"""Pure string-parsing helpers in app.heuristics that back extract_inputs/quantities.

These are exercised today only as a side effect of extract_inputs()/compile_text(),
so their individual branches (currency prefix/suffix, ranged values, currency
words, malformed tokens) have no direct assertions.
"""

from app.heuristics import (
    _normalize_currency,
    _tokenize_money_text,
    _match_money_token,
    _extract_money_candidate,
    estimate_complexity,
)


def test_normalize_currency_strips_spaces_and_swaps_comma_for_dot():
    assert _normalize_currency("1 000,50") == "1000.50"


def test_normalize_currency_leaves_plain_value_untouched():
    assert _normalize_currency("42") == "42"


def test_tokenize_money_text_splits_on_whitespace_and_hyphen_marker():
    tokens = _tokenize_money_text("Budget is $500-$700 for this")
    assert tokens == ["Budget", "is", "$500", "-", "$700", "for", "this"]


def test_tokenize_money_text_handles_en_dash_as_range_marker():
    tokens = _tokenize_money_text("100–200 TL")
    assert tokens == ["100", "-", "200", "TL"]


def test_match_money_token_matches_prefixed_dollar_amount():
    m = _match_money_token("$500")
    assert m is not None
    assert m.group("prefix") == "$"
    assert m.group("value") == "500"


def test_match_money_token_matches_suffixed_lira_symbol():
    m = _match_money_token("250₺")
    assert m is not None
    assert m.group("suffix") == "₺"


def test_match_money_token_rejects_non_numeric_token():
    assert _match_money_token("hello") is None


def test_match_money_token_strips_trailing_punctuation():
    m = _match_money_token("500.,")
    assert m is not None
    assert m.group("value") == "500"


def test_match_money_token_rejects_empty_after_stripping_punctuation():
    assert _match_money_token(",.") is None


def test_extract_money_candidate_finds_currency_word_after_number():
    result = _extract_money_candidate("It costs 500 tl to fix", require_currency=True)
    assert result == "500 tl"


def test_extract_money_candidate_requires_currency_when_asked():
    assert _extract_money_candidate("There were 500 people", require_currency=True) is None


def test_extract_money_candidate_allows_bare_number_without_currency_flag():
    result = _extract_money_candidate("There were 500 people", require_currency=False)
    assert result == "500"


def test_extract_money_candidate_handles_ranged_value():
    result = _extract_money_candidate("Between 100-200 usd", require_currency=True)
    assert result == "100-200 usd"


def test_extract_money_candidate_returns_none_when_no_number_present():
    assert _extract_money_candidate("no numbers here at all", require_currency=True) is None


def test_estimate_complexity_short_simple_text_is_low():
    assert estimate_complexity("Fix the bug") == "low"


def test_estimate_complexity_long_and_comparative_text_is_higher():
    long_text = " ".join(f"word{i}" for i in range(50))
    result = estimate_complexity(f"{long_text} please compare and explain the differences")
    assert result in ("medium", "high")


def test_estimate_complexity_teaching_and_comparison_signals_score_higher_than_plain_long_text():
    long_text = " ".join(f"word{i}" for i in range(50))
    plain_long = estimate_complexity(long_text)
    with_signals = estimate_complexity(f"{long_text} compare and explain and teach me")
    order = {"low": 0, "medium": 1, "high": 2}
    assert order[with_signals] >= order[plain_long]
