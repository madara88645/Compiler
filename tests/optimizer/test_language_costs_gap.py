"""tests/optimizer/test_language_costs_gap.py — direct unit tests for
app.optimizer.language_costs.count_estimated_tokens and get_openrouter_rates,
whose branches (empty text, tiktoken-missing fallback, prefix-match pricing,
unknown-model warning) were only exercised indirectly via estimate_prompt_cost.
"""

from unittest.mock import patch

from app.optimizer import language_costs
from app.optimizer.language_costs import (
    OPENROUTER_RATES,
    count_estimated_tokens,
    get_openrouter_rates,
)


# --- count_estimated_tokens ---


def test_count_estimated_tokens_empty_string_is_zero():
    assert count_estimated_tokens("") == 0


def test_count_estimated_tokens_none_like_falsy_is_zero():
    assert count_estimated_tokens(None) == 0  # type: ignore[arg-type]


def test_count_estimated_tokens_uses_tiktoken_when_available():
    text = "hello world, this is a short sentence."
    tokens = count_estimated_tokens(text)

    assert tokens > 0
    assert isinstance(tokens, int)


def test_count_estimated_tokens_falls_back_when_tiktoken_is_none():
    with patch.object(language_costs, "tiktoken", None):
        tokens = count_estimated_tokens("hello world")

    assert tokens > 0


def test_count_estimated_tokens_falls_back_on_encoding_exception():
    with patch.object(language_costs, "tiktoken") as mock_tiktoken:
        mock_tiktoken.get_encoding.side_effect = RuntimeError("encoding unavailable")
        tokens = count_estimated_tokens("hello world")

    assert tokens > 0


# --- get_openrouter_rates ---


def test_get_openrouter_rates_exact_match():
    input_rate, output_rate, warnings = get_openrouter_rates("openai/gpt-oss-20b")

    assert input_rate == OPENROUTER_RATES["openai/gpt-oss-20b"]["input"]
    assert output_rate == OPENROUTER_RATES["openai/gpt-oss-20b"]["output"]
    assert warnings == []


def test_get_openrouter_rates_prefix_match_falls_back_to_longest_key():
    # "openai/gpt-oss-120b-preview" isn't a registered key, but it starts with
    # the registered "openai/gpt-oss-120b" key, which should win over the
    # shorter "openai/gpt-oss-20b" prefix candidate.
    input_rate, output_rate, warnings = get_openrouter_rates("openai/gpt-oss-120b-preview")

    assert input_rate == OPENROUTER_RATES["openai/gpt-oss-120b"]["input"]
    assert output_rate == OPENROUTER_RATES["openai/gpt-oss-120b"]["output"]
    assert warnings == []


def test_get_openrouter_rates_unknown_model_returns_zero_with_warning():
    input_rate, output_rate, warnings = get_openrouter_rates("some/totally-unknown-model")

    assert input_rate == 0.0
    assert output_rate == 0.0
    assert len(warnings) == 1
    assert "some/totally-unknown-model" in warnings[0]


def test_get_openrouter_rates_empty_model_defaults_to_default_model():
    input_rate, output_rate, warnings = get_openrouter_rates("")

    assert input_rate == OPENROUTER_RATES[language_costs.DEFAULT_OPENROUTER_MODEL]["input"]
    assert warnings == []


def test_get_openrouter_rates_strips_whitespace():
    input_rate, output_rate, warnings = get_openrouter_rates("  openai/gpt-oss-20b  ")

    assert input_rate == OPENROUTER_RATES["openai/gpt-oss-20b"]["input"]
    assert warnings == []
