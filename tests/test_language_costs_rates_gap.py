"""Direct unit coverage for app.optimizer.language_costs.get_openrouter_rates
and count_estimated_tokens. Both are pure, static-table / offline-tokenizer
helpers exercised only indirectly today via estimate_prompt_cost, so the
prefix-matching fallback, the unknown-model $0 branch, and the tiktoken
except-guarded fallback have no direct assertions.
"""

import pytest

import app.optimizer.language_costs as language_costs
from app.optimizer.language_costs import (
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_RATES,
    count_estimated_tokens,
    get_openrouter_rates,
)
from app.text_utils import estimate_tokens


class TestGetOpenrouterRates:
    def test_exact_match_returns_configured_rates_with_no_warnings(self):
        input_rate, output_rate, warnings = get_openrouter_rates("qwen/qwen3-32b")
        assert input_rate == pytest.approx(0.08)
        assert output_rate == pytest.approx(0.28)
        assert warnings == []

    def test_default_model_used_when_empty_string_passed(self):
        input_rate, output_rate, warnings = get_openrouter_rates("")
        default_rates = OPENROUTER_RATES[DEFAULT_OPENROUTER_MODEL]
        assert input_rate == pytest.approx(default_rates["input"])
        assert output_rate == pytest.approx(default_rates["output"])
        assert warnings == []

    def test_default_model_used_when_none_passed(self):
        input_rate, output_rate, warnings = get_openrouter_rates(None)
        default_rates = OPENROUTER_RATES[DEFAULT_OPENROUTER_MODEL]
        assert input_rate == pytest.approx(default_rates["input"])
        assert warnings == []

    def test_prefix_fallback_matches_versioned_suffix(self):
        # "openai/gpt-oss-20b:free" isn't in the table verbatim but starts with
        # the known key "openai/gpt-oss-20b".
        input_rate, output_rate, warnings = get_openrouter_rates("openai/gpt-oss-20b:free")
        assert input_rate == pytest.approx(0.075)
        assert output_rate == pytest.approx(0.30)
        assert warnings == []

    def test_prefix_fallback_prefers_longest_matching_key(self):
        # "google/gemini-2.5-flash" is itself a prefix of "google/gemini-2.5-flash-lite".
        # A model id extending the -lite variant must resolve to -lite's rates,
        # not fall through to the shorter "flash" key.
        input_rate, output_rate, warnings = get_openrouter_rates(
            "google/gemini-2.5-flash-lite-preview"
        )
        assert input_rate == pytest.approx(0.10)
        assert output_rate == pytest.approx(0.40)
        assert warnings == []

    def test_prefix_fallback_does_not_over_match_shorter_sibling_key(self):
        # A suffix on the base "flash" model must resolve to the base flash
        # rates, since it does not start with the longer "-lite" key.
        input_rate, output_rate, warnings = get_openrouter_rates(
            "google/gemini-2.5-flash:extended-thinking"
        )
        assert input_rate == pytest.approx(0.30)
        assert output_rate == pytest.approx(2.50)
        assert warnings == []

    def test_unknown_model_returns_zero_rates_with_named_warning(self):
        input_rate, output_rate, warnings = get_openrouter_rates("totally/unknown-model")
        assert input_rate == 0.0
        assert output_rate == 0.0
        assert len(warnings) == 1
        assert "totally/unknown-model" in warnings[0]

    def test_whitespace_only_model_normalizes_to_empty_and_warns(self):
        input_rate, output_rate, warnings = get_openrouter_rates("   ")
        assert input_rate == 0.0
        assert output_rate == 0.0
        assert "''" in warnings[0]

    def test_model_with_surrounding_whitespace_is_stripped_before_lookup(self):
        input_rate, output_rate, warnings = get_openrouter_rates("  qwen/qwen3-32b  ")
        assert input_rate == pytest.approx(0.08)
        assert warnings == []


class TestCountEstimatedTokens:
    def test_empty_text_returns_zero(self):
        assert count_estimated_tokens("") == 0

    def test_nonempty_text_returns_positive_int_via_tiktoken(self):
        tokens = count_estimated_tokens("Hello world, this is a test sentence.")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_falls_back_to_estimate_tokens_when_tiktoken_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(language_costs, "tiktoken", None)
        text = "Bu fonksiyon icin guvenlik kisitlari yaz."
        assert count_estimated_tokens(text) == estimate_tokens(text)

    def test_falls_back_to_estimate_tokens_when_encoding_raises(self, monkeypatch):
        class _BoomEncoding:
            def get_encoding(self, name):
                raise RuntimeError("boom")

        monkeypatch.setattr(language_costs, "tiktoken", _BoomEncoding())
        text = "Some arbitrary prompt text for fallback coverage."
        assert count_estimated_tokens(text) == estimate_tokens(text)

    def test_falls_back_to_estimate_tokens_when_encode_raises(self, monkeypatch):
        class _BoomEncoder:
            def encode(self, text):
                raise ValueError("encode failure")

        class _FakeTiktoken:
            def get_encoding(self, name):
                return _BoomEncoder()

        monkeypatch.setattr(language_costs, "tiktoken", _FakeTiktoken())
        text = "Another prompt that triggers the except-guarded fallback path."
        assert count_estimated_tokens(text) == estimate_tokens(text)
