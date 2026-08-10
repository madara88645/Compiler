"""tests/test_llm_adapter.py — direct unit tests for app.llm.adapter's bidirectional
Executor <-> LLMProvider adapters, which had no dedicated test coverage. Both classes
are pure glue/mapping code exercised here with local fake doubles, no network/LLM calls.
"""

from typing import Any, Dict, Optional

from app.llm.adapter import ExecutorProvider, ProviderExecutor
from app.llm.base import LLMProvider, LLMResponse, ProviderConfig
from app.testing.runner import Executor


class FakeProvider(LLMProvider):
    """Records the last call and returns a fixed response."""

    def __init__(self, content: str = "fake response"):
        super().__init__(ProviderConfig(model="fake-model"))
        self._content = content
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return LLMResponse(content=self._content)


class FakeExecutor(Executor):
    """Records the last call and returns a fixed string."""

    def __init__(self, output: str = "fake output"):
        self._output = output
        self.last_prompt: Optional[str] = None
        self.last_config: Optional[Dict[str, Any]] = None

    def execute(self, prompt: str, config: Dict[str, Any]) -> str:
        self.last_prompt = prompt
        self.last_config = config
        return self._output


# --- ProviderExecutor (LLMProvider used as an Executor) ---


def test_provider_executor_delegates_to_provider_and_returns_content():
    provider = FakeProvider(content="hello from provider")
    executor = ProviderExecutor(provider)

    result = executor.execute("some prompt", {"model": "irrelevant", "temperature": 0.5})

    assert result == "hello from provider"
    assert provider.last_prompt == "some prompt"
    # ProviderExecutor treats the full prompt as the user prompt; no system_prompt is set.
    assert provider.last_system_prompt is None


def test_provider_executor_ignores_extra_config_keys():
    provider = FakeProvider(content="ok")
    executor = ProviderExecutor(provider)

    # config dict is currently unused by ProviderExecutor.execute; it should not raise
    # regardless of what's in it.
    result = executor.execute("prompt text", {"model": "x", "temperature": 1.0, "extra": "ignored"})

    assert result == "ok"


# --- ExecutorProvider (Executor used as an LLMProvider) ---


def test_executor_provider_generate_without_system_prompt():
    fake_executor = FakeExecutor(output="executor said hi")
    provider = ExecutorProvider(fake_executor)

    response = provider.generate(prompt="just the prompt")

    assert isinstance(response, LLMResponse)
    assert response.content == "executor said hi"
    assert fake_executor.last_prompt == "just the prompt"
    assert fake_executor.last_config == {}


def test_executor_provider_generate_concatenates_system_prompt():
    fake_executor = FakeExecutor(output="combined response")
    provider = ExecutorProvider(fake_executor)

    response = provider.generate(prompt="user part", system_prompt="system part")

    assert response.content == "combined response"
    assert fake_executor.last_prompt == "system part\n\nuser part"


def test_executor_provider_config_model_is_adapter_placeholder():
    provider = ExecutorProvider(FakeExecutor())

    assert provider.config.model == "executor-adapter"
