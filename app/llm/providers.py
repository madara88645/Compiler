from __future__ import annotations
import json
import time
import os
import httpx
from typing import Optional

from .base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """
    Deterministic mock provider for testing.
    Can be configured to fail or return specific JSON.
    """

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        start = time.time()

        # Simple heuristic to make tests pass if they want JSON
        content = "MOCKED RESPONSE"
        if "JSON" in (system_prompt or "") or "JSON" in prompt:
            content = json.dumps(
                {
                    "variations": [
                        {"type": "refinement", "prompt": "Mocked Refinement"},
                        {"type": "structural", "prompt": "Mocked Structural"},
                        {"type": "creative", "prompt": "Mocked Creative"},
                    ],
                    "passed": True,
                    "reason": "Mocked Pass",
                    "score": 1.0,
                }
            )

        latency = (time.time() - start) * 1000
        return LLMResponse(content=content, latency_ms=latency)


class OllamaProvider(LLMProvider):
    """
    Provider for local Ollama instance.
    Defaults to http://localhost:11434
    """

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        base_url = self.config.base_url or "http://localhost:11434"
        url = f"{base_url}/api/generate"

        if system_prompt:
            # Ollama supports system prompts in modelfile or via template,
            # but simplest is often just prepending for raw mode.
            # However, the /api/generate endpoint has a 'system' parameter.
            pass

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        start = time.time()
        try:
            # high timeout for local inference
            resp = httpx.post(url, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("response", "")

            # Ollama returns stats
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            }

        except Exception as e:
            return LLMResponse(content=f"Error: {str(e)}", latency_ms=0)

        latency = (time.time() - start) * 1000
        return LLMResponse(content=content, usage=usage, latency_ms=latency)


class OpenAIProvider(LLMProvider):
    """
    Provider for OpenAI API.
    Requires OPENAI_API_KEY env var or config.api_key.
    """

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return LLMResponse(content="Error: Missing OpenAI API Key", latency_ms=0)

        # We use httpx directly to avoid strict dependency on openai package if not installed,
        # but for robustness usually the package is better.
        # For this implementation plan, we will stick to httpx for lightweight dependency.

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        start = time.time()
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

        except Exception as e:
            return LLMResponse(content=f"Error: {str(e)}", latency_ms=0)

        latency = (time.time() - start) * 1000
        return LLMResponse(content=content, usage=usage, latency_ms=latency)
