from __future__ import annotations
import tiktoken
from typing import Dict, Tuple, List


class TokenCounter:
    """Handles token counting for various models using tiktoken."""

    @staticmethod
    def count(text: str, model: str) -> int:
        """
        Count tokens in the text for the specified model.
        Defaults to cl100k_base encoding if model is not found.
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Default to GPT-4/3.5 encoding if model unknown
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))


class PricingModel:
    """Defines pricing rates for supported models."""

    # Rates are in USD per 1,000,000 tokens
    RATES: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    }

    # Cache sorted keys for efficient prefix matching (longest first)
    _SORTED_KEYS: List[str] = sorted(RATES.keys(), key=len, reverse=True)

    @classmethod
    def get_rate(cls, model: str) -> Tuple[float, float]:
        """Returns (input_rate, output_rate) per 1M tokens for the model."""
        # Check longest matching prefix first to handle cases like "gpt-4o" vs "gpt-4o-mini"
        # We use a cached sorted list to avoid sorting on every call, but we must
        # fall back to sorting if _SORTED_KEYS is not consistent with RATES (e.g. during tests/mocking)

        keys_to_check = cls._SORTED_KEYS

        # If the keys have changed (e.g. due to mocking in tests), re-sort them
        if set(keys_to_check) != set(cls.RATES.keys()):
            keys_to_check = sorted(cls.RATES.keys(), key=len, reverse=True)

        for key in keys_to_check:
            if model.startswith(key):
                rate = cls.RATES[key]
                return rate["input"], rate["output"]

        # Default fallback (e.g. assume gpt-3.5-turbo pricing or 0 if unknown)
        return 0.0, 0.0


class CostTracker:
    """Tracks token usage and calculates estimated cost."""

    def __init__(self):
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    def add_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        """Accumulates usage and updates cost."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        input_rate, output_rate = PricingModel.get_rate(model)

        # Calculate cost: (tokens / 1M) * rate
        input_cost = (input_tokens / 1_000_000) * input_rate
        output_cost = (output_tokens / 1_000_000) * output_rate

        self.total_cost += input_cost + output_cost

    def estimated_cost(self) -> float:
        """Returns the total estimated cost in USD."""
        return self.total_cost
