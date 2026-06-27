"""
Tests for the Benchmark API router.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.auth import verify_api_key


@pytest.fixture
def client():
    """Create a test client with the benchmark router mounted."""
    from fastapi import FastAPI
    from app.routers.benchmark import router

    test_app = FastAPI()
    test_app.dependency_overrides[verify_api_key] = lambda: None
    test_app.include_router(router)

    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Unit tests for the heuristic judge
# ---------------------------------------------------------------------------


def test_heuristic_judge_both_empty():
    from app.routers.benchmark import _heuristic_judge

    result = _heuristic_judge("", "")
    assert "a_safety" in result
    assert "b_safety" in result
    assert "winner" in result


def test_heuristic_judge_improved_longer():
    from app.routers.benchmark import _heuristic_judge

    raw = "short answer"
    improved = "# Detailed Answer\n\n- Point one\n- Point two\n\nThis is a much more comprehensive response."
    result = _heuristic_judge(raw, improved)

    # Compiled should score higher on clarity due to markdown
    assert result["b_clarity"] >= result["a_clarity"]
    assert result["winner"] in ("A", "B")


def test_heuristic_judge_same_output():
    from app.routers.benchmark import _heuristic_judge

    text = "identical output"
    result = _heuristic_judge(text, text)

    # Same input → scores should be equal
    assert result["a_safety"] == result["b_safety"]
    assert result["a_clarity"] == result["b_clarity"]


# ---------------------------------------------------------------------------
# Integration test with mocked LLM
# ---------------------------------------------------------------------------


def test_benchmark_run_endpoint(client):
    """POST /benchmark/run should return valid BenchmarkResponse with nested metrics."""
    mock_raw = "Here is a basic answer about Python."
    mock_improved = "# Python Overview\n\n- Python is a high-level language\n- It supports OOP\n\n```python\nprint('hello')\n```"

    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
        # First call returns raw, second returns improved
        mock_llm.side_effect = [mock_raw, mock_improved]

        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": "openai/gpt-oss-20b"},
        )

    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert "raw_output" in data
    assert "compiled_prompt" in data
    assert "compiled_output" in data
    assert "improvement_score" in data
    assert "winner" in data
    assert "metrics" in data

    # Nested metrics matching frontend BenchmarkPayload
    metrics = data["metrics"]
    assert "safety" in metrics
    assert "clarity" in metrics
    assert "conciseness" in metrics
    assert "raw" in metrics["safety"]
    assert "compiled" in metrics["safety"]

    assert isinstance(data["improvement_score"], float)
    assert data["raw_output"] == mock_raw
    assert data["compiled_output"] == mock_improved


def test_benchmark_run_uses_selected_model_for_both_generations(client):
    """The requested benchmark model should be used for raw and compiled generations."""
    selected_model = "openai/gpt-oss-20b"

    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
        mock_llm.side_effect = ["raw output", "compiled output"]

        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": selected_model},
        )

    assert response.status_code == 200
    assert mock_llm.call_count == 2
    assert mock_llm.call_args_list[0].args[1] == selected_model
    assert mock_llm.call_args_list[1].args[1] == selected_model


def test_benchmark_run_short_prompt_with_valid_model(client):
    """A short prompt with a supported model should still succeed."""
    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
        mock_llm.return_value = "mock output"

        response = client.post(
            "/benchmark/run",
            json={"text": "hello", "model": "openai/gpt-oss-20b"},
        )

    assert response.status_code == 200


def test_benchmark_request_validation(client):
    """Missing required field 'text' should return 422."""
    response = client.post(
        "/benchmark/run",
        json={"model": "some-model"},
    )
    assert response.status_code == 422


def test_benchmark_request_rejects_invalid_model(client):
    """Unsupported benchmark models should be rejected by validation."""
    response = client.post(
        "/benchmark/run",
        json={"text": "Explain Python", "model": "not-a-real-model"},
    )

    assert response.status_code == 422


def test_benchmark_request_rejects_blank_text(client):
    """Blank prompts should be rejected before any LLM work starts."""
    response = client.post(
        "/benchmark/run",
        json={"text": "", "model": "openai/gpt-oss-20b"},
    )

    assert response.status_code == 422


def test_benchmark_provider_failure_returns_safe_error(client):
    """Provider/model failures should return a safe upstream error instead of a mock result."""
    with patch(
        "app.routers.benchmark._generate_llm_output",
        side_effect=RuntimeError("provider exploded"),
    ), patch("app.routers.benchmark._judge_with_llm", return_value=None):
        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": "openai/gpt-oss-20b"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Benchmark model request failed"


def test_judge_with_llm_handles_malformed_provider_response():
    """A malformed (non-JSON) judge response must degrade to None, not raise."""
    from unittest.mock import MagicMock

    import app.routers.benchmark as benchmark_mod

    fake_worker = MagicMock()
    fake_worker._call_api.return_value = "not valid json <<< {oops"
    fake_hybrid = MagicMock()
    fake_hybrid.worker = fake_worker

    with patch("api.main.hybrid_compiler", fake_hybrid):
        result = benchmark_mod._judge_with_llm("task", "raw output", "compiled output")

    assert result is None


def test_benchmark_run_succeeds_when_judge_response_is_malformed(client):
    """A malformed judge response must still yield a 200 via the heuristic fallback."""
    from unittest.mock import MagicMock

    fake_worker = MagicMock()
    # Judge returns non-JSON garbage -> _judge_with_llm returns None -> heuristic judge.
    fake_worker._call_api.return_value = "}}} not json"
    fake_hybrid = MagicMock()
    fake_hybrid.worker = fake_worker

    with patch(
        "app.routers.benchmark._generate_llm_output",
        side_effect=["raw output", "compiled output"],
    ), patch("api.main.hybrid_compiler", fake_hybrid):
        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": "openai/gpt-oss-20b"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_output"] == "raw output"
    assert data["compiled_output"] == "compiled output"
    assert data["winner"] in ("compiled", "raw")


def test_benchmark_models_are_loaded_from_shared_manifest():
    """Backend benchmark model validation should follow the shared frontend manifest."""
    from app.routers.benchmark import (
        DEFAULT_BENCHMARK_MODEL,
        SUPPORTED_BENCHMARK_MODELS,
        _load_benchmark_model_manifest,
    )

    manifest = _load_benchmark_model_manifest()
    manifest_ids = [item["id"] for item in manifest]

    assert tuple(manifest_ids) == SUPPORTED_BENCHMARK_MODELS
    assert DEFAULT_BENCHMARK_MODEL == manifest_ids[0]
