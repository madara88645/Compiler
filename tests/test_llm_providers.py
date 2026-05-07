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

        with patch("app.llm.providers.httpx.post", return_value=mock_response):
            response = provider.generate("Hello", system_prompt="Be concise")

        assert response.content == "Anthropic says hi"
        assert response.usage == {"prompt_tokens": 12, "completion_tokens": 34}

    def test_custom_config(self):
        config = ProviderConfig(model="custom-model", temperature=0.9)
        provider = get_provider("mock", config=config)

        assert provider.config.model == "custom-model"
        assert provider.config.temperature == 0.9


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
