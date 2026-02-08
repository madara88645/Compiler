from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app


# Mock the HybridCompiler to avoid real LLM calls
@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_api_optimize_basic_reduces_whitespace(mock_optimize):
    # Mock response: shorter version
    mock_optimize.return_value = "hello world"

    client = TestClient(app)
    text = "hello" + (" " * 120) + "world"

    r = client.post("/optimize", json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()

    assert isinstance(data["text"], str)
    assert data["text"] == "hello world"
    assert data["after_chars"] <= data["before_chars"]
    # Tokens should ideally be less or equal
    assert data["after_tokens"] <= data["before_tokens"]
    assert data["changed"] is True


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_api_optimize_preserves_fenced_code_block(mock_optimize):
    # Mock response: preserves code block
    code_block = (
        "Intro with spaces\n\n"
        "```python\n"
        "def foo():\n"
        "    return 1\n"
        "```\n\n"
        "Outro with spaces"
    )
    mock_optimize.return_value = code_block

    client = TestClient(app)
    text = (
        "Intro  with   spaces\n\n"
        "```python\n"
        "def  foo():\n"
        "    return  1\n"
        "```\n\n"
        "Outro  with   spaces\n"
    )

    r = client.post("/optimize", json={"text": text, "max_tokens": 1})
    assert r.status_code == 200, r.text
    optimized = r.json()["text"]

    assert "```python\n" in optimized
    assert "def foo():\n" in optimized  # Normalized spaces in mock
    assert "    return 1\n" in optimized
    assert "```\n" in optimized
