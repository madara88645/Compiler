from __future__ import annotations
import tiktoken
from typing import Dict, Tuple, Optional
from functools import lru_cache


# Module-level cache to avoid repeated encoding lookups
_ENCODER_CACHE = {}


class TokenCounter:
    """Handles token counting for various models using tiktoken."""

    @staticmethod
    def count(text: str, model: str) -> int:
        """
        Count tokens in the text for the specified model.
        Defaults to cl100k_base encoding if model is not found.
        """
        try:
            # Fast path: check local cache first
            encoding = _ENCODER_CACHE.get(model)
            if encoding is None:
                encoding = tiktoken.encoding_for_model(model)
                _ENCODER_CACHE[model] = encoding
        except KeyError:
            # Default to GPT-4/3.5 encoding if model unknown
            encoding = _ENCODER_CACHE.get("cl100k_base")
            if encoding is None:
                encoding = tiktoken.get_encoding("cl100k_base")
                _ENCODER_CACHE["cl100k_base"] = encoding
            # Note: we intentionally do not cache the fallback under the unknown
            # model name to avoid unbounded growth of _ENCODER_CACHE and sticky
            # mappings for dynamically introduced model identifiers.
        return len(encoding.encode(text))


class PricingModel:
    """Defines pricing rates for supported models."""

    # Rates are in USD per 1,000,000 tokens
    RATES: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    }

    # Track the set of known keys as a frozenset to catch all test mock changes (additions, removals, and swaps)
    # without allocating a new tuple/set on every call
    _KNOWN_KEYS_SET: frozenset[str] = frozenset(RATES.keys())
    # Cache sorted keys as a tuple to make it hashable for the lru_cache argument
    _SORTED_KEYS_TUPLE: Tuple[str, ...] = tuple(sorted(RATES.keys(), key=len, reverse=True))

    @staticmethod
    @lru_cache(maxsize=1024)
    def _get_prefix_key(model: str, sorted_keys: Tuple[str, ...]) -> Optional[str]:
        """Caches the O(N) prefix matching lookup using the standard library."""
        for key in sorted_keys:
            if model.startswith(key):
                return key
        return None

    @classmethod
    def get_rate(cls, model: str) -> Tuple[float, float]:
        """Returns (input_rate, output_rate) per 1M tokens for the model."""
        # Performance optimization: get_rate is on the hot path.
        # Check if the dictionary keys have changed (e.g., due to test mocking).
        # We compare a frozenset directly against the dict_keys view, which handles key
        # swaps correctly without allocating any new objects in the steady state.
        if cls._KNOWN_KEYS_SET != cls.RATES.keys():
            cls._KNOWN_KEYS_SET = frozenset(cls.RATES.keys())
            cls._SORTED_KEYS_TUPLE = tuple(sorted(cls.RATES.keys(), key=len, reverse=True))

        # Dynamically fetch the matching key from the bounded LRU cache.
        # The cache key includes `cls._SORTED_KEYS_TUPLE`, so cache invalidation is automatic
        # when the dictionary keys are modified during test mocks.
        matched_key = cls._get_prefix_key(model, cls._SORTED_KEYS_TUPLE)
        if matched_key:
            # Dynamically fetch the values from RATES ensuring we never return stale data
            # if a test patches only the pricing values of an existing key.
            rate = cls.RATES[matched_key]
            return rate["input"], rate["output"]

        # Default fallback
        return 0.0, 0.0


class CostTracker:
    """Tracks token usage and calculates estimated cost."""

    def __init__(self):
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    def add_usage(self, model: str, tokens: int, direction: str) -> None:
        """Accumulate token usage and costs."""
        input_rate, output_rate = PricingModel.get_rate(model)

        if direction == "input":
            self.total_input_tokens += tokens
            cost = (tokens / 1_000_000) * input_rate
        elif direction == "output":
            self.total_output_tokens += tokens
            cost = (tokens / 1_000_000) * output_rate
        else:
            cost = 0.0

        self.total_cost += cost

    def estimated_cost(self) -> float:
        """Returns the total estimated cost in USD."""
        return self.total_cost
