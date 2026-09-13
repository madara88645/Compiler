"""Verified OpenRouter model metadata used by optimizer estimates.

The catalog is intentionally a small, reviewed snapshot rather than a second
provider integration.  OpenRouter's model API is the source of truth for ids,
pricing, context limits, and tokenizer labels; refresh this file when those
values change.
"""

from __future__ import annotations

from dataclasses import dataclass


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_MODELS_DOCS_URL = (
    "https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties"
)
OPENROUTER_MODELS_GUIDE_URL = "https://openrouter.ai/docs/guides/overview/models"
CATALOG_VERIFIED_AT = "2026-09-12"


@dataclass(frozen=True)
class OpenRouterModel:
    """The metadata needed to label a token/cost estimate honestly."""

    id: str
    name: str
    tokenizer: str
    context_length: int
    input_rate_per_million: float
    output_rate_per_million: float
    verified_at: str = CATALOG_VERIFIED_AT
    source_url: str = OPENROUTER_MODELS_URL


# Rates below are the live Models API's per-token ``prompt`` and ``completion``
# values multiplied by 1,000,000 on 2026-09-12.  They are not provider guesses.
# Keep exact model ids: variants such as ``:batch`` can have different pricing.
OPENROUTER_MODEL_CATALOG: dict[str, OpenRouterModel] = {
    "openai/gpt-oss-20b": OpenRouterModel(
        id="openai/gpt-oss-20b",
        name="OpenAI: gpt-oss-20b",
        tokenizer="GPT",
        context_length=131_072,
        input_rate_per_million=0.03,
        output_rate_per_million=0.13,
    ),
    "openai/gpt-oss-120b": OpenRouterModel(
        id="openai/gpt-oss-120b",
        name="OpenAI: gpt-oss-120b",
        tokenizer="GPT",
        context_length=131_072,
        input_rate_per_million=0.037,
        output_rate_per_million=0.17,
    ),
    "mistralai/mistral-small-3.2-24b-instruct": OpenRouterModel(
        id="mistralai/mistral-small-3.2-24b-instruct",
        name="Mistral: Mistral Small 3.2 24B",
        tokenizer="Mistral",
        context_length=256_000,
        input_rate_per_million=0.075,
        output_rate_per_million=0.20,
    ),
    "qwen/qwen3-32b": OpenRouterModel(
        id="qwen/qwen3-32b",
        name="Qwen: Qwen3 32B",
        tokenizer="Qwen3",
        context_length=131_072,
        input_rate_per_million=0.08,
        output_rate_per_million=0.28,
    ),
    "deepseek/deepseek-v4.1-flash": OpenRouterModel(
        id="deepseek/deepseek-v4.1-flash",
        name="DeepSeek: DeepSeek V4.1 Flash",
        tokenizer="DeepSeek",
        context_length=1_048_576,
        input_rate_per_million=0.15,
        output_rate_per_million=0.60,
    ),
    "openai/gpt-5.6-luna": OpenRouterModel(
        id="openai/gpt-5.6-luna",
        name="OpenAI: GPT-5.6 Luna",
        tokenizer="GPT",
        context_length=1_050_000,
        input_rate_per_million=0.20,
        output_rate_per_million=1.20,
    ),
    "google/gemini-3.6-flash": OpenRouterModel(
        id="google/gemini-3.6-flash",
        name="Google: Gemini 3.6 Flash",
        tokenizer="Gemini",
        context_length=1_048_576,
        input_rate_per_million=0.75,
        output_rate_per_million=3.75,
    ),
    "google/gemini-2.5-flash-lite": OpenRouterModel(
        id="google/gemini-2.5-flash-lite",
        name="Google: Gemini 2.5 Flash Lite",
        tokenizer="Gemini",
        context_length=1_048_576,
        input_rate_per_million=0.10,
        output_rate_per_million=0.40,
    ),
    "google/gemini-2.5-flash": OpenRouterModel(
        id="google/gemini-2.5-flash",
        name="Google: Gemini 2.5 Flash",
        tokenizer="Gemini",
        context_length=1_048_576,
        input_rate_per_million=0.30,
        output_rate_per_million=2.50,
    ),
    # These legacy aliases are still live OpenRouter ids and keep the
    # evolutionary optimizer's existing configurations usable.
    "openai/gpt-4o": OpenRouterModel(
        id="openai/gpt-4o",
        name="OpenAI: GPT-4o",
        tokenizer="GPT",
        context_length=128_000,
        input_rate_per_million=2.50,
        output_rate_per_million=10.0,
    ),
    "openai/gpt-4o-mini": OpenRouterModel(
        id="openai/gpt-4o-mini",
        name="OpenAI: GPT-4o-mini",
        tokenizer="GPT",
        context_length=128_000,
        input_rate_per_million=0.15,
        output_rate_per_million=0.60,
    ),
    "openai/gpt-3.5-turbo": OpenRouterModel(
        id="openai/gpt-3.5-turbo",
        name="OpenAI: GPT-3.5 Turbo",
        tokenizer="GPT",
        context_length=16_385,
        input_rate_per_million=0.50,
        output_rate_per_million=1.50,
    ),
}


# Explicit aliases are kept separate from the catalog so an arbitrary prefix
# can never accidentally inherit another model's price.
LEGACY_MODEL_ALIASES: dict[str, str] = {
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
}


def canonical_model_id(model: str | None) -> str:
    normalized = (model or "").strip()
    return LEGACY_MODEL_ALIASES.get(normalized, normalized)


def get_model_metadata(model: str | None) -> OpenRouterModel | None:
    return OPENROUTER_MODEL_CATALOG.get(canonical_model_id(model))


def list_model_metadata() -> tuple[OpenRouterModel, ...]:
    return tuple(OPENROUTER_MODEL_CATALOG.values())
