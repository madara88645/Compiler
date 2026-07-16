"""Direct unit tests for the pure idea-density and ambiguity-detection helpers
in `app.heuristics.handlers.psycholinguist`.

Previously these were only exercised transitively through
`PsycholinguistHandler.handle()`, and no existing test asserted on
`idea_density` / `is_high_load` / `is_low_load` or on ambiguity diagnostics
directly, leaving the threshold boundaries untested.
"""

from app.heuristics.handlers.psycholinguist import (
    calculate_cognitive_load,
    detect_ambiguity,
)


# -----------------------------------------------------------------------------
# calculate_cognitive_load
# -----------------------------------------------------------------------------


def test_cognitive_load_high_density_single_sentence():
    text = (
        "analyze compute process transform validate execute optimize calculate "
        "integrate synthesize evaluate configure implement monitor deploy "
        "refactor document review test build"
    )

    result = calculate_cognitive_load(text)

    assert result.idea_density > 15
    assert result.is_high_load is True
    assert result.is_low_load is False
    assert result.suggestion == "Break this down into sub-tasks for clarity."


def test_cognitive_load_low_density_multiple_sentences():
    text = "Hi. Ok. Go."

    result = calculate_cognitive_load(text)

    assert result.idea_density == 0
    assert result.is_low_load is True
    assert result.is_high_load is False
    assert result.suggestion == "Consider summarizing to focus the request."


def test_cognitive_load_moderate_density_has_no_suggestion():
    text = "The quick brown fox jumps over lazy dog today morning."

    result = calculate_cognitive_load(text)

    assert 3 <= result.idea_density <= 15
    assert result.is_high_load is False
    assert result.is_low_load is False
    assert result.suggestion is None


def test_cognitive_load_exact_threshold_is_not_high_load():
    # Exactly 15 words of 4+ chars in a single sentence -> density == 15,
    # which must NOT trip the `> 15` high-load branch.
    words = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "theta",
        "iota",
        "kappa",
        "lambda",
        "sigma",
        "omega",
        "value",
        "index",
        "logic",
    ]
    text = " ".join(words)
    assert len(words) == 15

    result = calculate_cognitive_load(text)

    assert result.idea_density == 15
    assert result.is_high_load is False


def test_cognitive_load_empty_text_defaults_to_single_sentence_zero_density():
    result = calculate_cognitive_load("")

    assert result.idea_density == 0
    assert result.is_high_load is False
    assert result.is_low_load is False
    assert result.suggestion is None


# -----------------------------------------------------------------------------
# detect_ambiguity
# -----------------------------------------------------------------------------


def test_detect_ambiguity_no_vague_terms():
    result = detect_ambiguity("Write a Python function that reverses a string using recursion.")

    assert result.is_ambiguous is False
    assert result.ambiguous_terms == []
    assert result.suggestions == []


def test_detect_ambiguity_fix_it_pattern():
    result = detect_ambiguity("Please fix it for me.")

    assert result.is_ambiguous is True
    assert "fix_it" in result.ambiguous_terms


def test_detect_ambiguity_better_pattern():
    result = detect_ambiguity("Please make it better.")

    assert result.is_ambiguous is True
    assert "better" in result.ambiguous_terms


def test_detect_ambiguity_clean_up_pattern():
    result = detect_ambiguity("Let's clean up this code.")

    assert result.is_ambiguous is True
    assert "clean_up" in result.ambiguous_terms


def test_detect_ambiguity_stuff_pattern():
    result = detect_ambiguity("There is some stuff to consider.")

    assert result.is_ambiguous is True
    assert "stuff" in result.ambiguous_terms


def test_detect_ambiguity_multiple_patterns_detected_together():
    result = detect_ambiguity("Please fix it and clean up the stuff, make it better.")

    assert result.is_ambiguous is True
    assert set(result.ambiguous_terms) == {"fix_it", "clean_up", "stuff", "better"}
    assert len(result.suggestions) == 4


def test_detect_ambiguity_is_case_insensitive():
    result = detect_ambiguity("FIX IT NOW")

    assert result.is_ambiguous is True
    assert "fix_it" in result.ambiguous_terms
