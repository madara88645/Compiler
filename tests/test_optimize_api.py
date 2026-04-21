from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app


# Mock the HybridCompiler to avoid real LLM calls
@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_api_optimize_basic_reduces_whitespace(mock_optimize):
    # Mock response: shorter version (tuple of content + usage)
    mock_optimize.return_value = ("hello world", None)

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
    assert data["provider"] == "groq"
    assert data["model"] == "llama-3.1-8b-instant"
    assert data["source_language"] == "en"
    assert data["tokenizer_method"].endswith(":estimated")
    assert data["estimated_input_cost_usd"] > data["estimated_output_cost_usd"]
    assert data["estimated_savings_usd"] > 0
    assert "saved_percent" in data


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
    mock_optimize.return_value = (code_block, None)

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


@patch("app.llm_engine.client.WorkerClient.optimize_prompt_english_variant")
@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_api_optimize_returns_english_variant_without_replacing_main_output(
    mock_optimize, mock_english_variant
):
    turkish_text = (
        "PDF'i ozetle. Junior gelistirici icin uygulama plani yaz. Guvenlik kisitlarini koru."
    )
    english_text = (
        "Summarize PDF. Write implementation plan for junior developer. Keep safety constraints."
    )
    mock_optimize.return_value = (turkish_text, None)
    mock_english_variant.return_value = (english_text, None)

    client = TestClient(app)
    text = (
        "Bu PDF'i ozetle ve junior bir gelistirici icin net bir uygulama plani yaz. "
        "Guvenlik kisitlarini ve {{project_name}} degiskenini koru."
    )

    r = client.post("/optimize", json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["text"] == turkish_text
    assert data["english_variant"] == english_text
    assert data["english_variant"] != data["text"]
    assert data["english_variant_tokens"] > 0
    assert data["english_variant_cost_usd"] > 0
    assert data["source_language"] == "tr"
    assert any("review" in warning.lower() for warning in data["warnings"])


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_optimizer_strips_wrapper_label_prefix(mock_optimize):
    mock_optimize.return_value = ("**Optimized Prompt**:\nClean body text", None)

    client = TestClient(app)
    r = client.post("/optimize", json={"text": "verbose original input text"})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["text"] == "Clean body text"
    assert "Optimized Prompt" not in data["text"]


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_optimizer_preserves_code_fences_and_placeholders(mock_optimize):
    body = (
        "Write Python function with {{user_level}} placeholder.\n\n"
        "```python\n"
        "def greet(name):\n"
        "    return f'hello {name}'\n"
        "```\n"
    )
    mock_optimize.return_value = (body, None)

    client = TestClient(app)
    r = client.post(
        "/optimize",
        json={
            "text": (
                "Please write a Python function with a {{user_level}} placeholder. "
                "Show me a small example."
            )
        },
    )
    assert r.status_code == 200, r.text
    optimized = r.json()["text"]

    assert "{{user_level}}" in optimized
    assert "```python" in optimized
    assert "def greet(name):" in optimized
    assert "```\n" in optimized


@patch("app.llm_engine.client.WorkerClient.optimize_prompt_english_variant")
@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_main_optimized_output_preserves_turkish_language(mock_optimize, mock_english_variant):
    mock_optimize.return_value = ("Summarize the document and write a plan.", None)
    mock_english_variant.return_value = ("Summarize the document and write a plan.", None)

    client = TestClient(app)
    text = "Bu dokümanı özetle ve geliştirici için plan yaz."
    r = client.post("/optimize", json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["source_language"] == "tr"
    assert any("language differs" in warning.lower() for warning in data["warnings"])


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_optimize_warns_when_after_tokens_exceed_before_tokens(mock_optimize):
    mock_optimize.return_value = (
        (
            "This optimized output is intentionally much longer than the input it received "
            "so that the after_tokens count exceeds the before_tokens count by a wide margin."
        ),
        None,
    )

    client = TestClient(app)
    r = client.post("/optimize", json={"text": "short"})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["after_tokens"] > data["before_tokens"]
    assert any("more tokens" in warning.lower() for warning in data["warnings"])


@patch("app.llm_engine.client.WorkerClient.optimize_prompt_english_variant")
@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_english_variant_failure_emits_warning(mock_optimize, mock_english_variant):
    mock_optimize.return_value = ("PDF'i ozetle ve plan yaz.", None)
    mock_english_variant.side_effect = RuntimeError("rate limited")

    client = TestClient(app)
    text = "Bu PDF'i ozetle ve plan yaz."
    r = client.post("/optimize", json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["english_variant"] == ""
    assert any(
        "english compact suggestion unavailable" in warning.lower() for warning in data["warnings"]
    )


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_optimize_falls_back_with_pricing_warning(mock_optimize):
    mock_optimize.return_value = ("hello world", None)

    client = TestClient(app)
    r = client.post(
        "/optimize",
        json={"text": "hello world", "model": "not-a-real-model"},
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["estimated_input_cost_usd"] == 0
    assert data["estimated_output_cost_usd"] == 0
    assert any("not-a-real-model" in warning for warning in data["warnings"])


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_optimize_usage_is_request_scoped(mock_optimize):
    """Guard against the pre-fix race: concurrent callers must not see each other's usage dict.

    The worker is a shared singleton; if usage leaks through instance state
    then whichever request finishes last will overwrite the other's metrics.
    With the tuple return each request carries its own usage payload.
    """
    from concurrent.futures import ThreadPoolExecutor

    def fake_optimize(user_text, max_tokens=None, max_chars=None):
        # Return different usage dicts so we can detect cross-request bleed.
        if "alpha" in user_text:
            return ("alpha-out", {"prompt_tokens": 11, "completion_tokens": 22})
        return ("beta-out", {"prompt_tokens": 99, "completion_tokens": 88})

    mock_optimize.side_effect = fake_optimize

    client = TestClient(app)

    def post(text):
        return client.post("/optimize", json={"text": text}).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        alpha_future = pool.submit(post, "alpha request body")
        beta_future = pool.submit(post, "beta request body")
        alpha = alpha_future.result()
        beta = beta_future.result()

    assert alpha["text"] == "alpha-out"
    assert beta["text"] == "beta-out"
    assert alpha["optimizer_call_usage"] == {"prompt_tokens": 11, "completion_tokens": 22}
    assert beta["optimizer_call_usage"] == {"prompt_tokens": 99, "completion_tokens": 88}
