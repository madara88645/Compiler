"""Factory for instantiating LLM providers based on configuration."""

from __future__ import annotations
import os
from typing import Optional

from .base import LLMProvider, ProviderConfig
from .providers import MockProvider, OllamaProvider, OpenAIProvider

# Registry of available providers
PROVIDERS = {
    "mock": MockProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
}


def get_provider(
    name: Optional[str] = None, config: Optional[ProviderConfig] = None
) -> LLMProvider:
    """
    Factory to instantiate LLM providers based on name and config.

    Args:
        name: Provider name ("mock", "ollama", "openai").
              If None, reads from PROMPTC_LLM_PROVIDER env var, defaults to "mock".
        config: Optional ProviderConfig. If None, creates from env vars.

    Returns:
        Instantiated LLMProvider.

    Raises:
        ValueError: If provider name is not recognized.
    """
    # Resolve provider name
    if name is None:
        name = os.environ.get("PROMPTC_LLM_PROVIDER", "mock").lower()
    else:
        name = name.lower()

    # Validate provider
    if name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    # Build config from env vars if not provided
    if config is None:
        config = ProviderConfig(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("PROMPTC_LLM_BASE_URL"),
            model=os.environ.get("PROMPTC_LLM_MODEL", "gpt-4o"),
            temperature=float(os.environ.get("PROMPTC_LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.environ.get("PROMPTC_LLM_MAX_TOKENS", "2048")),
            timeout=float(os.environ.get("PROMPTC_LLM_TIMEOUT", "30.0")),
        )

    # Instantiate and return
    provider_class = PROVIDERS[name]
    return provider_class(config)


def register_provider(name: str, provider_class: type) -> None:
    """
    Register a custom provider class.

    Args:
        name: Name to register the provider under.
        provider_class: Class that inherits from LLMProvider.
    """
    if not issubclass(provider_class, LLMProvider):
        raise TypeError(f"{provider_class} must be a subclass of LLMProvider")
    PROVIDERS[name.lower()] = provider_class
