"""Unit tests for pure utility helpers in app/emitters.py.

Functions under test have no external dependencies (no env reads, no I/O,
no model imports) and are safe to call in isolation.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.emitters import (
    _clean_domain_suggestion_text,
    _contains_any_marker,
    _is_trivial_input,
    _minimal_greeting_prompt,
    _relevant_followups,
    _scenario_considerations,
)


class TestIsTrivialInput:
    """Short/greeting inputs below the 30-char threshold in the general domain."""

    def test_short_general_low_is_trivial(self) -> None:
        assert _is_trivial_input("hi", "general", "low") is True

    def test_short_general_none_complexity_is_trivial(self) -> None:
        assert _is_trivial_input("hello", "general", None) is True  # type: ignore[arg-type]

    def test_short_general_empty_complexity_is_trivial(self) -> None:
        assert _is_trivial_input("hey", "general", "") is True

    def test_non_general_domain_not_trivial(self) -> None:
        assert _is_trivial_input("hi", "coding", "low") is False

    def test_long_text_not_trivial(self) -> None:
        long_text = "a" * 30
        assert _is_trivial_input(long_text, "general", "low") is False

    def test_high_complexity_not_trivial(self) -> None:
        assert _is_trivial_input("hi", "general", "high") is False

    def test_leading_trailing_whitespace_stripped_before_length_check(self) -> None:
        # 28 spaces + "hi" = 30 chars total, but stripped = "hi" (2 chars) → trivial
        assert _is_trivial_input("  hi  ", "general", "low") is True

    def test_exactly_29_chars_is_trivial(self) -> None:
        assert _is_trivial_input("a" * 29, "general", "low") is True


class TestContainsAnyMarker:
    """Fast-path substring search over a tuple of marker strings."""

    def test_matching_marker_returns_true(self) -> None:
        assert _contains_any_marker("merhaba arkadas", ("merhaba", "selam")) is True

    def test_second_marker_matches(self) -> None:
        assert _contains_any_marker("hey selam", ("merhaba", "selam")) is True

    def test_no_matching_marker_returns_false(self) -> None:
        assert _contains_any_marker("hello world", ("merhaba", "selam")) is False

    def test_empty_text_returns_false(self) -> None:
        assert _contains_any_marker("", ("merhaba",)) is False

    def test_empty_markers_returns_false(self) -> None:
        assert _contains_any_marker("merhaba", ()) is False

    def test_case_sensitive_no_match(self) -> None:
        assert _contains_any_marker("MERHABA", ("merhaba",)) is False

    def test_partial_substring_match(self) -> None:
        assert _contains_any_marker("slm nasilsin", ("slm",)) is True


class TestMinimalGreetingPrompt:
    """Language detection and prompt structure for short/greeting inputs."""

    def test_english_text_returns_english_prompt(self) -> None:
        result = _minimal_greeting_prompt("hi", "en")
        assert 'User message: "hi"' in result
        assert "Reply briefly" in result

    def test_turkish_lang_returns_turkish_prompt(self) -> None:
        result = _minimal_greeting_prompt("hey", "tr")
        assert 'Kullanici mesaji: "hey"' in result
        assert "Asagidaki" in result

    def test_turkish_marker_in_english_lang_returns_turkish_prompt(self) -> None:
        result = _minimal_greeting_prompt("merhaba", "en")
        assert "Asagidaki" in result
        assert 'Kullanici mesaji: "merhaba"' in result

    def test_empty_text_en_defaults_to_hello(self) -> None:
        result = _minimal_greeting_prompt("", "en")
        assert 'User message: "hello"' in result

    def test_empty_text_tr_defaults_to_merhaba(self) -> None:
        result = _minimal_greeting_prompt("", "tr")
        assert 'Kullanici mesaji: "merhaba"' in result

    def test_whitespace_collapsed_in_output(self) -> None:
        result = _minimal_greeting_prompt("hello   world", "en")
        assert 'User message: "hello world"' in result

    def test_slm_marker_triggers_turkish_prompt(self) -> None:
        result = _minimal_greeting_prompt("slm", "en")
        assert "Asagidaki" in result


class TestCleanDomainSuggestionText:
    """Strips short prefixes before named action markers."""

    def test_no_prefix_returns_unchanged(self) -> None:
        assert _clean_domain_suggestion_text("Include error handling") == "Include error handling"

    def test_tip_prefix_stripped_before_include(self) -> None:
        assert _clean_domain_suggestion_text("Tip: Include logging") == "Include logging"

    def test_short_prefix_stripped_before_add(self) -> None:
        assert _clean_domain_suggestion_text("A: Add validation") == "Add validation"

    def test_numbered_prefix_stripped_before_consider(self) -> None:
        assert _clean_domain_suggestion_text("1. Consider edge cases") == "Consider edge cases"

    def test_long_prefix_not_stripped(self) -> None:
        # Marker at position > 8 → not stripped
        text = "Some long prefix Add something"
        assert _clean_domain_suggestion_text(text) == text

    def test_empty_string_returns_empty(self) -> None:
        assert _clean_domain_suggestion_text("") == ""

    def test_whitespace_normalized(self) -> None:
        result = _clean_domain_suggestion_text("  Review   the code  ")
        assert result == "Review the code"

    def test_ok_prefix_stripped_before_use(self) -> None:
        assert _clean_domain_suggestion_text("Ok: Use type hints") == "Use type hints"


class TestScenarioConsiderations:
    """Route conservative scenario guidance only when the right signals appear."""

    def test_browser_download_requires_all_three_signals(self) -> None:
        ir = SimpleNamespace(
            goals=["Add a button so users can download CSV exports from the dashboard"],
            tasks=[],
        )

        considerations = _scenario_considerations(ir)

        assert len(considerations) == 2
        assert "Blob + an <a download> link" in considerations[0]
        assert "File System Access API is unsupported in Safari" in considerations[1]

    def test_browser_download_does_not_trigger_without_feature_adding_verb(self) -> None:
        ir = SimpleNamespace(
            goals=["Fix the Safari CSV download that opens inline instead of saving"],
            tasks=[],
        )

        assert _scenario_considerations(ir) == []

    def test_react_perf_requires_react_and_perf_markers(self) -> None:
        ir = SimpleNamespace(
            goals=["My React list is slow and re-renders too much when filters change"],
            tasks=[],
        )

        considerations = _scenario_considerations(ir)

        assert len(considerations) == 2
        assert "React DevTools Profiler" in considerations[0]
        assert "virtualize long lists" in considerations[1]


class TestRelevantFollowups:
    """Choose the most useful follow-up question set for the prompt context."""

    def test_react_perf_prompt_prefers_perf_followups_over_browser_keywords(self) -> None:
        ir = SimpleNamespace(
            goals=["My React button re-renders constantly and the page feels slow"],
            tasks=[],
            intents=[],
            domain="software",
        )

        followups = _relevant_followups(ir)

        assert len(followups) == 3
        assert "React DevTools Profiler" in followups[0]
        assert "Which browser and version is affected" not in "\n".join(followups)

    def test_browser_bug_prompt_gets_browser_followups(self) -> None:
        ir = SimpleNamespace(
            goals=["This Chrome button renders in the wrong place after click"],
            tasks=[],
            intents=[],
            domain="software",
        )

        followups = _relevant_followups(ir)

        assert len(followups) == 3
        assert followups[0].startswith("Which browser and version is affected")

    def test_generic_api_optimization_prompt_falls_back_to_software_followups(self) -> None:
        ir = SimpleNamespace(
            goals=["Optimize this API and make it better"],
            tasks=[],
            intents=[],
            domain="software",
        )

        followups = _relevant_followups(ir)

        assert len(followups) == 3
        assert followups[0] == "Which language, framework, and version are targeted?"
        assert "React DevTools Profiler" not in "\n".join(followups)
