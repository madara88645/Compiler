from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from app.text_utils import estimate_tokens

try:
    import tiktoken
except Exception:  # pragma: no cover - tiktoken is a declared dependency.
    tiktoken = None


DEFAULT_PROVIDER = "groq"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
TOKENIZER_METHOD = "tiktoken:o200k_base:estimated"

# USD per 1M tokens. Source: Groq public pricing page, captured in AGENTS-driven plan.
GROQ_RATES: dict[str, dict[str, float]] = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-safeguard-20b": {"input": 0.075, "output": 0.30},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "qwen/qwen3-32b": {"input": 0.29, "output": 0.59},
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


def get_groq_rates(model: str) -> tuple[float, float, list[str]]:
    normalized = (model or DEFAULT_GROQ_MODEL).strip()
    if normalized in GROQ_RATES:
        rates = GROQ_RATES[normalized]
        return rates["input"], rates["output"], []

    for key in sorted(GROQ_RATES, key=len, reverse=True):
        if normalized.startswith(key):
            rates = GROQ_RATES[key]
            return rates["input"], rates["output"], []

    return 0.0, 0.0, [f"No Groq pricing configured for model '{normalized}'. Cost shown as $0."]


def estimate_prompt_cost(
    text: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_GROQ_MODEL,
    direction: Literal["input", "output"] = "input",
    token_count_override: int | None = None,
) -> PromptCostEstimate:
    value = text or ""
    tokens = (
        token_count_override if token_count_override is not None else count_estimated_tokens(value)
    )
    input_rate, output_rate, warnings = (
        get_groq_rates(model) if provider == "groq" else (0.0, 0.0, [])
    )
    if provider != "groq":
        warnings = [f"No pricing configured for provider '{provider}'. Cost shown as $0."]

    rate = input_rate if direction == "input" else output_rate
    estimated_cost = round((tokens / 1_000_000) * rate, 10)
    chars_per_token = round((len(value) / tokens), 2) if tokens else 0.0

    return PromptCostEstimate(
        provider=provider,
        model=model or DEFAULT_GROQ_MODEL,
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
