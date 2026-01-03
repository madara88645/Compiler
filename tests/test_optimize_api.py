from fastapi.testclient import TestClient

from api.main import app


def test_api_optimize_basic_reduces_whitespace():
    client = TestClient(app)
    text = "hello" + (" " * 120) + "world"

    r = client.post("/optimize", json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()

    assert isinstance(data["text"], str)
    assert data["after_chars"] <= data["before_chars"]
    assert data["after_tokens"] <= data["before_tokens"]
    assert data["changed"] is True


def test_api_optimize_preserves_fenced_code_block():
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
    assert "def  foo():\n" in optimized
    assert "    return  1\n" in optimized
    assert "```\n" in optimized
