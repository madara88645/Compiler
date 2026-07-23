from app.optimizer.language_costs import (
    DEFAULT_OPENROUTER_MODEL,
    count_estimated_tokens,
    get_openrouter_rates,
)


# --------------------------------------------------------------------------
# count_estimated_tokens
# --------------------------------------------------------------------------


def test_count_estimated_tokens_empty_string_is_zero():
    assert count_estimated_tokens("") == 0


def test_count_estimated_tokens_returns_positive_count_for_text():
    assert count_estimated_tokens("hello world, this is a short prompt") > 0


def test_count_estimated_tokens_scales_with_input_length():
    short = count_estimated_tokens("hello")
    long = count_estimated_tokens("hello " * 50)
    assert long > short


# --------------------------------------------------------------------------
# get_openrouter_rates
# --------------------------------------------------------------------------


def test_get_openrouter_rates_exact_match_returns_configured_rates_with_no_warnings():
    input_rate, output_rate, warnings = get_openrouter_rates("openai/gpt-oss-20b")
    assert input_rate == 0.075
    assert output_rate == 0.30
    assert warnings == []


def test_get_openrouter_rates_blank_model_falls_back_to_default():
    input_rate, output_rate, warnings = get_openrouter_rates("")
    default_input, default_output, default_warnings = get_openrouter_rates(
        DEFAULT_OPENROUTER_MODEL
    )
    assert (input_rate, output_rate, warnings) == (default_input, default_output, default_warnings)


def test_get_openrouter_rates_strips_whitespace_before_matching():
    input_rate, output_rate, warnings = get_openrouter_rates("  openai/gpt-oss-20b  ")
    assert (input_rate, output_rate) == (0.075, 0.30)
    assert warnings == []


def test_get_openrouter_rates_prefix_match_for_unlisted_variant():
    # "openai/gpt-oss-20b-preview" isn't a configured key, but should match
    # the longest configured prefix, "openai/gpt-oss-20b".
    input_rate, output_rate, warnings = get_openrouter_rates("openai/gpt-oss-20b-preview")
    assert (input_rate, output_rate) == (0.075, 0.30)
    assert warnings == []


def test_get_openrouter_rates_unknown_model_returns_zero_cost_with_warning():
    input_rate, output_rate, warnings = get_openrouter_rates("totally/unknown-model")
    assert (input_rate, output_rate) == (0.0, 0.0)
    assert len(warnings) == 1
    assert "totally/unknown-model" in warnings[0]
