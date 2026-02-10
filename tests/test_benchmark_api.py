"""
Tests for the Benchmark API router.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with the benchmark router mounted."""
    from fastapi import FastAPI
    from app.routers.benchmark import router

    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Unit tests for the mock judge
# ---------------------------------------------------------------------------


def test_mock_judge_both_empty():
    from app.routers.benchmark import _mock_judge_evaluate

    assert _mock_judge_evaluate("", "") == 0.0


def test_mock_judge_improved_longer():
    from app.routers.benchmark import _mock_judge_evaluate

    raw = "short answer"
    improved = "# Detailed Answer\n\n- Point one\n- Point two\n\nThis is a much more comprehensive response."
    score = _mock_judge_evaluate(raw, improved)
    assert 0.0 < score <= 1.0


def test_mock_judge_same_output():
    from app.routers.benchmark import _mock_judge_evaluate

    text = "identical output"
    score = _mock_judge_evaluate(text, text)
    # No length improvement, no struct bonus, just the base 0.1
    assert score == 0.1


# ---------------------------------------------------------------------------
# Integration test with mocked LLM
# ---------------------------------------------------------------------------


def test_benchmark_run_endpoint(client):
    """POST /benchmark/run should return valid BenchmarkResponse."""
    mock_raw = "Here is a basic answer about Python."
    mock_improved = "# Python Overview\n\n- Python is a high-level language\n- It supports OOP\n\n```python\nprint('hello')\n```"

    with patch("app.routers.benchmark._generate_llm_output") as mock_llm:
        # First call returns raw, second returns improved
        mock_llm.side_effect = [mock_raw, mock_improved]

        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": "llama-3.1-8b-instant"},
        )

    assert response.status_code == 200
    data = response.json()

    assert "raw_output" in data
    assert "compiled_prompt" in data
    assert "compiled_output" in data
    assert "improvement_score" in data
    assert "winner" in data
    assert "metrics" in data
    assert isinstance(data["improvement_score"], float)
    assert data["raw_output"] == mock_raw
    assert data["compiled_output"] == mock_improved


def test_benchmark_run_empty_prompt(client):
    """Should handle empty prompt gracefully (compiler still works)."""
    with patch("app.routers.benchmark._generate_llm_output") as mock_llm:
        mock_llm.return_value = "mock output"

        response = client.post(
            "/benchmark/run",
            json={"text": "hello", "model": "test-model"},
        )

    assert response.status_code == 200


def test_benchmark_request_validation(client):
    """Missing required field 'text' should return 422."""
    response = client.post(
        "/benchmark/run",
        json={"model": "some-model"},
    )
    assert response.status_code == 422
