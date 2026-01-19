from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""
    content: str
    raw_response: Any = None
    usage: Dict[str, int] = Field(default_factory=dict) # e.g. {"prompt_tokens": 10, "completion_tokens": 20}
    latency_ms: float = 0.0

class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: float = 30.0

class LLMProvider(ABC):
    """Abstract Base Class for LLM Providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate a text completion.
        
        Args:
            prompt: The user prompt.
            system_prompt: Optional system instruction.
            
        Returns:
            LLMResponse object containing content and metadata.
        """
        pass
