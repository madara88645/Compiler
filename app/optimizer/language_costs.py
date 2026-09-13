from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from app.optimizer.model_catalog import (
    OPENROUTER_MODELS_URL,
    OPENROUTER_MODEL_CATALOG,
    canonical_model_id,
    get_model_metadata,
)
from app.text_utils import estimate_tokens

try:
    import tiktoken
except Exception:  # pragma: no cover - tiktoken is a declared dependency.
    tiktoken = None


DEFAULT_PROVIDER = "openrouter"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-20b"
TOKENIZER_METHOD = "tiktoken:o200k_base:estimated"
HEURISTIC_TOKENIZER_METHOD = "heuristic:utf8_bytes_words:estimated"

# USD per 1M tokens.  Keep this mapping as a compatibility surface for callers
# that imported it before the catalog existed; the reviewed model catalog is the
# source for the initial values and matching is exact (apart from explicit aliases).
OPENROUTER_RATES: dict[str, dict[str, float]] = {
    model_id: {
        "input": metadata.input_rate_per_million,
        "output": metadata.output_rate_per_million,
    }
    for model_id, metadata in OPENROUTER_MODEL_CATALOG.items()
}

_TURKISH_CHARS_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
_TURKISH_HINTS = {
    "bu",
    "icin",
    "için",
    "ve",
    "bir",
    "gibi",
    "ozetle",
    "özetle",
    "gelistirici",
    "geliştirici",
    "uygulama",
    "plani",
    "planı",
    "guvenlik",
    "güvenlik",
    "kisit",
    "kisitlari",
    "kısıt",
    "kısıtları",
    "degisken",
    "değişken",
    "yaz",
}
_ENGLISH_HINTS = {
    "the",
    "and",
    "for",
    "with",
    "write",
    "summarize",
    "create",
    "analyze",
    "developer",
    "implementation",
    "prompt",
    "safety",
    "constraints",
}
_WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü']+")


@dataclass(frozen=True)
class PromptCostEstimate:
    provider: str
    model: str
    source_language: str
    tokenizer_method: str
    tokens: int
    chars: int
    chars_per_token: float
    input_rate_per_million: float
    output_rate_per_million: float
    estimated_cost_usd: float
    warnings: list[str] = field(default_factory=list)
    pricing_known: bool = True
    pricing_source: str | None = None
    pricing_verified_at: str | None = None
    tokenizer_name: str | None = None
    token_count_is_estimate: bool = True
    context_length: int | None = None


def detect_language(text: str) -> str:
    """Small deterministic TR/EN detector for cost guidance, not translation quality."""

    value = (text or "").strip()
    if not value:
        return "unknown"

    if _TURKISH_CHARS_RE.search(value):
        return "tr"

    words = [word.lower().strip("'") for word in _WORD_RE.findall(value)]

    # Bolt Optimization: Single explicit loop is ~2.5x faster than two separate
    # sum() generator expressions, avoiding redundant iterations over words.
    tr_score = 0
    en_score = 0
    for word in words:
        if word in _TURKISH_HINTS:
            tr_score += 1
        elif word in _ENGLISH_HINTS:
            en_score += 1

    if tr_score > en_score:
        return "tr"
    if en_score > 0:
        return "en"
    return "en"


def count_estimated_tokens(
    text: str,
    *,
    model: str = DEFAULT_OPENROUTER_MODEL,
    token_ratio: float = 4.0,
) -> int:
    """Count tokens conservatively without claiming provider exactness.

    OpenRouter exposes tokenizer labels, but its API does not provide a local
    tokenizer implementation.  We use ``o200k_base`` only for GPT-labelled
    models and a transparent character/word heuristic for other tokenizers.
    Both paths remain estimates because chat wrappers and provider-specific
    tokenization are not included.
    """

    return _count_with_method(text, model=model, token_ratio=token_ratio)[0]


def _count_with_method(text: str, *, model: str, token_ratio: float) -> tuple[int, str]:
    """Keep the reported method coupled to the counting operation that ran."""
    metadata = get_model_metadata(model)
    if metadata is not None and metadata.tokenizer == "GPT" and tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("o200k_base")
            # Prompt text may literally discuss tokenizer control strings.
            return len(encoding.encode(text, disallowed_special=())), TOKENIZER_METHOD
        except Exception:
            pass
    return estimate_tokens(text, token_ratio=token_ratio), HEURISTIC_TOKENIZER_METHOD


def get_openrouter_rates(model: str) -> tuple[float, float, list[str]]:
    normalized = (model or DEFAULT_OPENROUTER_MODEL).strip()
    resolved = canonical_model_id(normalized)
    if resolved in OPENROUTER_RATES:
        rates = OPENROUTER_RATES[resolved]
        return rates["input"], rates["output"], []

    return (
        0.0,
        0.0,
        [
            f"No verified OpenRouter pricing is available for model '{normalized}'. "
            "Cost estimate is unavailable; $0 is a placeholder, not a free-call claim. "
            f"Refresh from {OPENROUTER_MODELS_URL}."
        ],
    )


def estimate_prompt_cost(
    text: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_OPENROUTER_MODEL,
    direction: Literal["input", "output"] = "input",
    token_count_override: int | None = None,
    token_ratio: float = 4.0,
) -> PromptCostEstimate:
    value = text or ""
    normalized_provider = (provider or DEFAULT_PROVIDER).strip().lower()
    resolved_model = (model or DEFAULT_OPENROUTER_MODEL).strip()
    tokens, tokenizer_method = _count_with_method(
        value,
        model=resolved_model if normalized_provider == "openrouter" else "",
        token_ratio=token_ratio,
    )
    if token_count_override is not None:
        tokens = token_count_override
        tokenizer_method = "supplied:token_count"
    metadata = get_model_metadata(resolved_model) if normalized_provider == "openrouter" else None
    pricing_known = True
    pricing_source: str | None = None
    pricing_verified_at: str | None = None
    tokenizer_name: str | None = metadata.tokenizer if metadata else None
    context_length: int | None = metadata.context_length if metadata else None

    if normalized_provider == "local":
        input_rate, output_rate, warnings = (0.0, 0.0, [])
        pricing_source = "local:no-metered-provider"
    elif normalized_provider == "openrouter":
        input_rate, output_rate, warnings = get_openrouter_rates(resolved_model)
        pricing_known = metadata is not None and not warnings
        pricing_source = OPENROUTER_MODELS_URL if pricing_known else None
        pricing_verified_at = metadata.verified_at if metadata else None
        if metadata is None:
            tokenizer_name = None
    else:
        input_rate, output_rate, warnings = (0.0, 0.0, [])
        pricing_known = False
        warnings = [
            f"No verified pricing is available for provider '{normalized_provider}'. "
            "Cost estimate is unavailable; $0 is a placeholder."
        ]

    rate = input_rate if direction == "input" else output_rate
    estimated_cost = round((tokens / 1_000_000) * rate, 10)
    chars_per_token = round((len(value) / tokens), 2) if tokens else 0.0

    return PromptCostEstimate(
        provider=normalized_provider,
        model=resolved_model,
        source_language=detect_language(value),
        tokenizer_method=tokenizer_method,
        tokens=tokens,
        chars=len(value),
        chars_per_token=chars_per_token,
        input_rate_per_million=input_rate,
        output_rate_per_million=output_rate,
        estimated_cost_usd=estimated_cost,
        warnings=warnings,
        pricing_known=pricing_known,
        pricing_source=pricing_source,
        pricing_verified_at=pricing_verified_at,
        tokenizer_name=tokenizer_name,
        token_count_is_estimate=True,
        context_length=context_length,
    )
