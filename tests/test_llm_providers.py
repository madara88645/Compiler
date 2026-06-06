"""Tests for LLM providers and factory."""

import os
from unittest.mock import MagicMock, patch
import pytest

from app.llm.base import LLMProvider, ProviderConfig, LLMResponse
from app.llm.providers import AnthropicProvider, MockProvider, OllamaProvider, OpenAIProvider
from app.llm.factory import get_provider, register_provider, PROVIDERS


class TestProviderConfig:
    def test_default_values(self):
        config = ProviderConfig()
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_custom_values(self):
        config = ProviderConfig(model="llama3", temperature=0.5)
        assert config.model == "llama3"
        assert config.temperature == 0.5


class TestMockProvider:
    def test_basic_response(self):
        config = ProviderConfig()
        provider = MockProvider(config)
        response = provider.generate("Hello")

        assert isinstance(response, LLMResponse)
        assert "MOCKED" in response.content

    def test_json_response(self):
        config = ProviderConfig()
        provider = MockProvider(config)
        response = provider.generate("Give me JSON", system_prompt="Return JSON")

        assert "variations" in response.content or "passed" in response.content


class TestFactory:
    def test_get_mock_provider(self):
        provider = get_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_get_ollama_provider(self):
        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_get_openai_provider(self):
        provider = get_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_get_anthropic_provider(self):
        provider = get_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown_provider")

    def test_case_insensitive(self):
        provider = get_provider("MOCK")
        assert isinstance(provider, MockProvider)

        provider = get_provider("OpenAI")
        assert isinstance(provider, OpenAIProvider)

    def test_env_var_default(self):
        with patch.dict(os.environ, {"PROMPTC_LLM_PROVIDER": "ollama"}):
            provider = get_provider()
            assert isinstance(provider, OllamaProvider)

    def test_anthropic_env_defaults(self):
        with patch.dict(os.environ, {"PROMPTC_LLM_PROVIDER": "anthropic"}, clear=False):
            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)
            assert provider.config.model == "claude-opus-4-7"


class TestAnthropicProvider:
    def test_missing_api_key_returns_error(self):
        config = ProviderConfig()
        provider = AnthropicProvider(config)

        response = provider.generate("Hello")

        assert response.content == "Error: Missing Anthropic API Key"

    def test_successful_response(self):
        config = ProviderConfig(api_key="test-key", model="claude-opus-4-7")
        provider = AnthropicProvider(config)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Anthropic says hi"}],
            "usage": {"input_tokens": 12, "output_tokens": 34},
        }

        with patch.object(provider.client, "post", return_value=mock_response):
            response = provider.generate("Hello", system_prompt="Be concise")

        assert response.content == "Anthropic says hi"
        assert response.usage == {"prompt_tokens": 12, "completion_tokens": 34}

    def test_custom_config(self):
        config = ProviderConfig(model="custom-model", temperature=0.9)
        provider = get_provider("mock", config=config)

        assert provider.config.model == "custom-model"
        assert provider.config.temperature == 0.9


class TestOpenAIProvider:
    def test_missing_api_key_returns_error_without_making_request(self):
        config = ProviderConfig()
        provider = OpenAIProvider(config)

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False), patch.object(
            provider.client, "post"
        ) as mock_post:
            response = provider.generate("Hello")

        assert response.content == "Error: Missing OpenRouter API Key"
        mock_post.assert_not_called()

    def test_successful_response_uses_persistent_client_and_openrouter_headers(self):
        config = ProviderConfig(api_key="test-key", model="openai/gpt-oss-20b", timeout=12.5)
        provider = OpenAIProvider(config)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter says hi"}}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 8},
        }

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
                "OPENROUTER_HTTP_REFERER": "https://promptc.example",
                "OPENROUTER_TITLE": "Prompt Compiler",
            },
            clear=False,
        ), patch.object(provider.client, "post", return_value=mock_response) as mock_post:
            response = provider.generate(
                "Hello",
                system_prompt="Be concise",
                model="openai/gpt-oss-120b",
                temperature=0.2,
                max_tokens=321,
            )

        assert response.content == "OpenRouter says hi"
        assert response.usage == {"prompt_tokens": 21, "completion_tokens": 8}
        mock_post.assert_called_once()
        url = mock_post.call_args.args[0]
        kwargs = mock_post.call_args.kwargs
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        assert kwargs["timeout"] == 12.5
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert kwargs["headers"]["HTTP-Referer"] == "https://promptc.example"
        assert kwargs["headers"]["X-Title"] == "Prompt Compiler"
        assert kwargs["json"]["model"] == "openai/gpt-oss-120b"
        assert kwargs["json"]["temperature"] == 0.2
        assert kwargs["json"]["max_tokens"] == 321
        assert kwargs["json"]["messages"] == [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ]

    def test_http_failures_return_generic_error(self):
        config = ProviderConfig(api_key="test-key")
        provider = OpenAIProvider(config)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = RuntimeError("boom")

        with patch.object(provider.client, "post", return_value=mock_response):
            response = provider.generate("Hello")

        assert response.content == "Error: An internal error occurred."


class TestOllamaProvider:
    def test_successful_response_maps_usage_and_system_prompt(self):
        config = ProviderConfig(base_url="http://ollama.local:11434", model="llama3")
        provider = OllamaProvider(config)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "response": "Local model says hi",
            "prompt_eval_count": 13,
            "eval_count": 5,
        }

        with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
            response = provider.generate(
                "Hello",
                system_prompt="Answer precisely",
                temperature=0.2,
                max_tokens=99,
            )

        assert response.content == "Local model says hi"
        assert response.usage == {"prompt_tokens": 13, "completion_tokens": 5}
        mock_post.assert_called_once()
        url = mock_post.call_args.args[0]
        kwargs = mock_post.call_args.kwargs
        assert url == "http://ollama.local:11434/api/generate"
        assert kwargs["timeout"] == 60.0
        assert kwargs["json"]["model"] == "llama3"
        assert kwargs["json"]["prompt"] == "Hello"
        assert kwargs["json"]["stream"] is False
        assert kwargs["json"]["options"] == {"temperature": 0.2, "num_predict": 99}
        assert kwargs["json"]["system"] == "Answer precisely"


class TestRegisterProvider:
    def test_register_custom_provider(self):
        class CustomProvider(LLMProvider):
            def generate(self, prompt, system_prompt=None):
                return LLMResponse(content="Custom!")

        register_provider("custom", CustomProvider)
        assert "custom" in PROVIDERS

        provider = get_provider("custom")
        assert isinstance(provider, CustomProvider)

    def test_register_non_provider_raises(self):
        class NotAProvider:
            pass

        with pytest.raises(TypeError):
            register_provider("bad", NotAProvider)
