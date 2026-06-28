"""
Denial-of-Wallet protection for the public /benchmark/run endpoint.

The benchmark endpoint is intentionally public (no API key) but triggers
server-side LLM generation, so it must be protected from anonymous abuse
WITHOUT requiring end-user credentials. Two layers:

1. Per-IP rate limiting: /benchmark belongs to the "heavy" route group.
2. A global daily cap on benchmark runs (a backstop that per-IP limits
   cannot provide, since an attacker can rotate IPs).
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Bare app with only the benchmark router mounted (matches test_benchmark_api)."""
    from app.routers.benchmark import router

    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


@pytest.fixture
def reset_daily_cap():
    """Isolate the global benchmark daily-cap state for cap tests."""
    import api.auth as auth

    auth.reset_benchmark_daily_state()
    yield
    auth.reset_benchmark_daily_state()


def _post(client, ip: str):
    return client.post(
        "/benchmark/run",
        json={"text": "Explain Python", "model": "openai/gpt-oss-20b"},
        headers={"x-forwarded-for": ip},
    )


def test_benchmark_route_is_in_heavy_rate_limit_group():
    """/benchmark/run must be classified 'heavy' so its per-IP limit is the strict one."""
    from api.auth import _get_route_group

    assert _get_route_group("/benchmark/run") == "heavy"


def test_benchmark_daily_cap_blocks_globally_after_limit(client, monkeypatch, reset_daily_cap):
    """Once the global daily run limit is hit, further runs get 429 even from new IPs."""
    monkeypatch.setenv("BENCHMARK_DAILY_RUN_LIMIT", "2")

    with patch(
        "app.routers.benchmark._generate_llm_output", side_effect=lambda *a, **k: "out"
    ), patch("app.routers.benchmark._judge_with_llm", return_value=None):
        # Two distinct IPs each succeed (proves the cap is global, not per-IP).
        assert _post(client, "1.1.1.1").status_code == 200
        assert _post(client, "2.2.2.2").status_code == 200
        # A third run from yet another IP is blocked by the global daily cap.
        blocked = _post(client, "3.3.3.3")

    assert blocked.status_code == 429
    assert "daily" in blocked.json()["detail"].lower()


def test_benchmark_daily_cap_resets_on_new_utc_day(client, monkeypatch, reset_daily_cap):
    """A counter left over from a previous day must not block today's runs."""
    import api.auth as auth

    monkeypatch.setenv("BENCHMARK_DAILY_RUN_LIMIT", "1")
    # Simulate yesterday's bucket already maxed out.
    auth._BENCHMARK_DAILY_STATE["date"] = "2000-01-01"
    auth._BENCHMARK_DAILY_STATE["count"] = 9999

    with patch(
        "app.routers.benchmark._generate_llm_output", side_effect=lambda *a, **k: "out"
    ), patch("app.routers.benchmark._judge_with_llm", return_value=None):
        response = _post(client, "1.1.1.1")

    assert response.status_code == 200
    today = datetime.now(timezone.utc).date().isoformat()
    assert auth._BENCHMARK_DAILY_STATE["date"] == today
    assert auth._BENCHMARK_DAILY_STATE["count"] == 1
