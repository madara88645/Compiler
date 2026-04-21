import pytest

from app.optimizer.language_costs import (
    DEFAULT_GROQ_MODEL,
    detect_language,
    estimate_prompt_cost,
)


def test_turkish_prompt_can_cost_more_tokens_than_english_equivalent():
    english = "Summarize this PDF and write a clear implementation plan for a junior developer."
    turkish = "Bu PDF'i ozetle ve birinci sinif bir gelistirici icin net bir uygulama plani yaz."

    english_estimate = estimate_prompt_cost(english)
    turkish_estimate = estimate_prompt_cost(turkish)

    assert english_estimate.provider == "groq"
    assert english_estimate.model == DEFAULT_GROQ_MODEL
    assert english_estimate.source_language == "en"
    assert turkish_estimate.source_language == "tr"
    assert turkish_estimate.tokens > english_estimate.tokens
    assert turkish_estimate.estimated_cost_usd > english_estimate.estimated_cost_usd
    assert turkish_estimate.tokenizer_method.endswith(":estimated")


def test_default_groq_llama_31_8b_pricing_is_applied():
    estimate = estimate_prompt_cost("hello world", token_count_override=1_000_000)

    assert estimate.input_rate_per_million == pytest.approx(0.05)
    assert estimate.output_rate_per_million == pytest.approx(0.08)
    assert estimate.estimated_cost_usd == pytest.approx(0.05)


def test_unknown_model_returns_zero_cost_with_warning():
    estimate = estimate_prompt_cost("hello world", model="unknown-model")

    assert estimate.tokens > 0
    assert estimate.estimated_cost_usd == 0.0
    assert any("unknown-model" in warning for warning in estimate.warnings)


def test_detect_language_returns_tr_for_turkish_with_diacritics():
    assert detect_language("Bu fonksiyon için güvenlik kısıtları yaz.") == "tr"


def test_detect_language_returns_tr_for_diacritic_free_turkish_keywords():
    assert detect_language("Bu fonksiyon icin guvenlik kisitlari yaz") == "tr"


def test_detect_language_returns_en_for_short_english_phrase():
    assert detect_language("Write a function that validates email addresses.") == "en"


def test_detect_language_returns_unknown_only_for_empty_input():
    assert detect_language("") == "unknown"
    assert detect_language("   \n\t") == "unknown"
    assert detect_language("hello") == "en"
