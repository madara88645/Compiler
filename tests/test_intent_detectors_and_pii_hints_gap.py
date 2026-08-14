"""Direct unit tests for pure heuristic helpers that were previously only
exercised indirectly through compile_text()/detect_pii() integration tests:
the keyword-based intent detectors and the PII false-positive hint window.
"""
from app.heuristics import (
    _contains_any_keyword,
    _has_fp_hint_around_match,
    detect_creative_intent,
    detect_explanation_intent,
    detect_preparation_intent,
    detect_proposal_intent,
    detect_review_intent,
)


# --- _contains_any_keyword ------------------------------------------------


def test_contains_any_keyword_match():
    assert _contains_any_keyword("Please explain this to me", ["explain", "clarify"]) is True


def test_contains_any_keyword_no_match():
    assert _contains_any_keyword("Write a poem about the sea", ["explain", "clarify"]) is False


def test_contains_any_keyword_case_insensitive():
    assert _contains_any_keyword("EXPLAIN this concept", ["explain"]) is True


def test_contains_any_keyword_empty_keywords():
    assert _contains_any_keyword("anything at all", []) is False


def test_contains_any_keyword_substring_match():
    assert _contains_any_keyword("unexplainable phenomena", ["explain"]) is True


# --- detect_creative_intent -----------------------------------------------


def test_detect_creative_intent_true():
    assert detect_creative_intent("Write a short story about a dragon") is True


def test_detect_creative_intent_tagline_keyword():
    assert detect_creative_intent("I need a tagline for my new app") is True


def test_detect_creative_intent_false():
    assert detect_creative_intent("What is the capital of France?") is False


# --- detect_explanation_intent ---------------------------------------------


def test_detect_explanation_intent_true():
    assert detect_explanation_intent("Can you explain how recursion works?") is True


def test_detect_explanation_intent_walk_me_through():
    assert detect_explanation_intent("Walk me through the deployment process") is True


def test_detect_explanation_intent_false():
    assert detect_explanation_intent("Write me a poem") is False


# --- detect_proposal_intent -------------------------------------------------


def test_detect_proposal_intent_true():
    assert detect_proposal_intent("I need to pitch this idea to my manager") is True


def test_detect_proposal_intent_suggest_a_strategy():
    assert detect_proposal_intent("Suggest a strategy for entering this market") is True


def test_detect_proposal_intent_false():
    assert detect_proposal_intent("What time is it in Tokyo?") is False


# --- detect_review_intent ---------------------------------------------------


def test_detect_review_intent_true():
    assert detect_review_intent("Can you review this pull request?") is True


def test_detect_review_intent_check_my():
    assert detect_review_intent("Check my essay for grammar mistakes") is True


def test_detect_review_intent_false():
    assert detect_review_intent("Generate a random password") is False


# --- detect_preparation_intent -----------------------------------------------


def test_detect_preparation_intent_true():
    assert detect_preparation_intent("Prepare me for my interview next week") is True


def test_detect_preparation_intent_mock_interview():
    assert detect_preparation_intent("I want a mock interview for a backend role") is True


def test_detect_preparation_intent_false():
    assert detect_preparation_intent("Summarize this article") is False


# --- _has_fp_hint_around_match ------------------------------------------------


def test_fp_hint_present_before_match():
    text = "Here is an example SSN: 123-45-6789 used in docs"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_fp_hint_present_after_match():
    text = "SSN 123-45-6789 is just a placeholder value"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_fp_hint_absent():
    text = "My actual SSN is 123-45-6789, please keep it private"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is False


def test_fp_hint_exactly_at_window_boundary():
    # "mask" (4 chars) is placed so it starts exactly at (start - window),
    # i.e. its full span is included in the lookback window.
    window = 24
    hint = "mask"
    filler = "xxx"
    spacer = " " * (window - len(hint))
    text = filler + hint + spacer + "1234567890"
    start = len(filler) + len(hint) + len(spacer)
    end = start + 10
    assert start - window == len(filler)  # sanity: hint starts exactly at lo
    assert _has_fp_hint_around_match(text, start, end, window=window) is True


def test_fp_hint_just_outside_window_boundary():
    # Same layout, but one extra space pushes the hint's last character
    # one position outside the lookback window, so it must not be found.
    window = 24
    hint = "mask"
    filler = "xxx"
    spacer = " " * (window - len(hint) + 1)
    text = filler + hint + spacer + "1234567890"
    start = len(filler) + len(hint) + len(spacer)
    end = start + 10
    assert _has_fp_hint_around_match(text, start, end, window=window) is False


def test_fp_hint_respects_string_bounds():
    # start/end at the very edges of the string must not raise, even when
    # start - window or end + window fall outside the string bounds.
    text = "dummy 123"
    start = text.index("123")
    end = len(text)
    assert _has_fp_hint_around_match(text, start, end, window=50) is True
