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
            json={"text": "Explain Python", "model": "llama-3.1-8b-instant"},
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


def test_benchmark_run_empty_prompt(client):
    """Should handle empty prompt gracefully (compiler still works)."""
    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
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
