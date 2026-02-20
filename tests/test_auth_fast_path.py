import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from api.main import app
from api.auth import APIKey, SessionLocal

client = TestClient(app)


# Mock DB or insert test key
@pytest.fixture
def test_key():
    db = SessionLocal()
    key = APIKey(key="sk_test_123", owner="pytest")
    db.add(key)
    try:
        db.commit()
    except Exception:
        db.rollback()

    yield "sk_test_123"

    # Cleanup
    db.delete(key)
    db.commit()
    db.close()


def test_compile_fast_no_key():
    resp = client.post("/compile/fast", json={"text": "hello"})
    assert resp.status_code == 403


def test_compile_fast_invalid_key():
    resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": "invalid"})
    assert resp.status_code == 403


def test_compile_fast_success(test_key):
    # Mock hybrid_compiler to avoid actual LLM calls
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir.model_dump.return_value = {}
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"

        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": test_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["heuristic_version"] == "v2-fast"
        assert "processing_ms" in data


def test_rate_limit(test_key):
    # Depending on how the rate limiter is implemented (in-memory global),
    # we might need to reset it or just spam enough requests.
    from api.auth import RATE_LIMIT_STORE

    RATE_LIMIT_STORE.clear()

    # Send 10 requests (allowed)
    for _ in range(10):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.return_value = MagicMock(
                ir=MagicMock(model_dump=lambda: {}),
                system_prompt="",
                user_prompt="",
                plan="",
                optimized_content="",
            )
            client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})

    # 11th request should fail
    with patch("api.main.hybrid_compiler") as mock:
        mock.cache = {}
        resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
        assert resp.status_code == 429
