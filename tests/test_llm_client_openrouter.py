from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.llm_engine.client import WorkerClient


def test_worker_client_prefers_openrouter_env_defaults():
    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_MODEL": "openai/gpt-oss-20b",
            "OPENROUTER_HTTP_REFERER": "https://prcompiler.com",
            "OPENROUTER_TITLE": "Prompt Compiler",
        },
        clear=False,
    ), patch("app.llm_engine.client.OpenAI") as mock_openai:
        client = WorkerClient()

    assert client.api_key == "or-key"
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.model == "openai/gpt-oss-20b"
    mock_openai.assert_called_once()
    _, kwargs = mock_openai.call_args
    assert kwargs["default_headers"]["HTTP-Referer"] == "https://prcompiler.com"
    assert kwargs["default_headers"]["X-Title"] == "Prompt Compiler"


def test_call_api_requires_parameter_support_for_openrouter_json_mode():
    with patch("app.llm_engine.client.OpenAI") as mock_openai:
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage=None,
        )
        create_mock = MagicMock(return_value=completion)
        mock_openai.return_value = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )
        client = WorkerClient(
            api_key="or-key",
            base_url="https://openrouter.ai/api/v1",
            model="openai/gpt-oss-20b",
        )

        response = client._call_api([{"role": "user", "content": "hello"}], json_mode=True)

    assert response == '{"ok":true}'
    _, kwargs = create_mock.call_args
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"]["provider"]["require_parameters"] is True
