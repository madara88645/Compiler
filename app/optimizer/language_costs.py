from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from app.text_utils import estimate_tokens

try:
    import tiktoken
except Exception:  # pragma: no cover - tiktoken is a declared dependency.
    tiktoken = None


DEFAULT_PROVIDER = "openrouter"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-20b"
TOKENIZER_METHOD = "tiktoken:o200k_base:estimated"

# USD per 1M tokens.
OPENROUTER_RATES: dict[str, dict[str, float]] = {
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "google/gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "mistralai/mistral-small-3.2-24b-instruct": {"input": 0.075, "output": 0.20},
    "qwen/qwen3-32b": {"input": 0.08, "output": 0.28},
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


def count_estimated_tokens(text: str) -> int:
    if not text:
        return 0
    if tiktoken is None:
        return estimate_tokens(text)
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text))
    except Exception:
        return estimate_tokens(text)


def get_openrouter_rates(model: str) -> tuple[float, float, list[str]]:
    normalized = (model or DEFAULT_OPENROUTER_MODEL).strip()
    if normalized in OPENROUTER_RATES:
        rates = OPENROUTER_RATES[normalized]
        return rates["input"], rates["output"], []

    for key in sorted(OPENROUTER_RATES, key=len, reverse=True):
        if normalized.startswith(key):
            rates = OPENROUTER_RATES[key]
            return rates["input"], rates["output"], []

    return (
        0.0,
        0.0,
        [f"No OpenRouter pricing configured for model '{normalized}'. Cost shown as $0."],
    )


def estimate_prompt_cost(
    text: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_OPENROUTER_MODEL,
    direction: Literal["input", "output"] = "input",
    token_count_override: int | None = None,
) -> PromptCostEstimate:
    value = text or ""
    normalized_provider = (provider or DEFAULT_PROVIDER).strip().lower()
    resolved_model = (model or DEFAULT_OPENROUTER_MODEL).strip()
    tokens = (
        token_count_override if token_count_override is not None else count_estimated_tokens(value)
    )
    if normalized_provider == "local":
        input_rate, output_rate, warnings = (0.0, 0.0, [])
    elif normalized_provider == "openrouter":
        input_rate, output_rate, warnings = get_openrouter_rates(resolved_model)
    else:
        input_rate, output_rate, warnings = (0.0, 0.0, [])
        warnings = [
            f"No pricing configured for provider '{normalized_provider}'. Cost shown as $0."
        ]

    rate = input_rate if direction == "input" else output_rate
    estimated_cost = round((tokens / 1_000_000) * rate, 10)
    chars_per_token = round((len(value) / tokens), 2) if tokens else 0.0

    return PromptCostEstimate(
        provider=normalized_provider,
        model=resolved_model,
        source_language=detect_language(value),
        tokenizer_method=TOKENIZER_METHOD,
        tokens=tokens,
        chars=len(value),
        chars_per_token=chars_per_token,
        input_rate_per_million=input_rate,
        output_rate_per_million=output_rate,
        estimated_cost_usd=estimated_cost,
        warnings=warnings,
    )
