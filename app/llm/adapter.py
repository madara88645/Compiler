from typing import Dict, Any, Optional
from app.testing.runner import Executor
from app.llm.base import LLMProvider, LLMResponse, ProviderConfig


class ProviderExecutor(Executor):
    """
    Adapter that allows an LLMProvider to be used where an Executor is expected.
    (e.g. inside TestRunner and LLMJudge)
    """

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def execute(self, prompt: str, config: Dict[str, Any]) -> str:
        # Map config to strict args if needed, or just ignore since ProviderConfig handles most
        # Executor 'config' meant per-call overrides, but our simplified Provider generate()
        # relies on its internal config mostly, or we could pass temp/max_tokens if we updated base.
        # For now, simple pass-through.

        # Note: Executor.execute receives the FULL prompt (system + user usually merged).
        # We treat it as user prompt.
        response = self.provider.generate(prompt=prompt)
        return response.content


class ExecutorProvider(LLMProvider):
    """
    Adapter that allows an Executor to be used where an LLMProvider is expected.
    (e.g. inside LLMJudge when initialized by legacy TestRunner)
    """

    def __init__(self, executor: Executor):
        self.executor = executor
        # Dummy config
        super().__init__(ProviderConfig(model="executor-adapter"))

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        # Executor doesn't return metadata, so we mock usage/latency
        content = self.executor.execute(full_prompt, {})
        return LLMResponse(content=content)
