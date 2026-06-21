"""Unit tests for app.token_optimizer — pure text-optimization helpers."""

from __future__ import annotations

from app.token_optimizer import (
    OptimizeStats,
    _is_fence_close,
    _looks_like_table_row,
    _meets_budget,
    _normalize_fence_boundaries,
    _normalize_line,
    _split_fenced_code,
    optimize_text,
)


class TestIsFenceClose:
    def test_backtick_fence_closes(self):
        assert _is_fence_close("```\n", "```") is True

    def test_tilde_fence_closes(self):
        assert _is_fence_close("~~~\n", "~~~") is True

    def test_longer_backtick_fence_closes_shorter_marker(self):
        assert _is_fence_close("````\n", "```") is True

    def test_fence_with_language_tag_does_not_close(self):
        # "```python" → strip("``") yields "python" which is truthy → not a close
        assert _is_fence_close("```python\n", "```") is False

    def test_blank_line_does_not_close(self):
        assert _is_fence_close("\n", "```") is False

    def test_empty_fence_marker_returns_false(self):
        assert _is_fence_close("```\n", "") is False

    def test_mismatched_fence_char_returns_false(self):
        assert _is_fence_close("~~~\n", "```") is False


class TestLooksLikeTableRow:
    def test_two_pipes_detected(self):
        assert _looks_like_table_row("| col1 | col2 |") is True

    def test_three_pipes_detected(self):
        assert _looks_like_table_row("| a | b | c |") is True

    def test_single_pipe_not_table(self):
        assert _looks_like_table_row("echo foo | bar") is False

    def test_no_pipes_not_table(self):
        assert _looks_like_table_row("regular text line") is False


class TestMeetsBudget:
    def test_no_budget_always_meets(self):
        assert _meets_budget("any text", max_chars=None, max_tokens=None) is True

    def test_within_char_budget(self):
        assert _meets_budget("hello", max_chars=10, max_tokens=None) is True

    def test_exceeds_char_budget(self):
        assert _meets_budget("hello world", max_chars=5, max_tokens=None) is False

    def test_exactly_at_char_budget(self):
        assert _meets_budget("hello", max_chars=5, max_tokens=None) is True

    def test_empty_text_meets_zero_budget(self):
        assert _meets_budget("", max_chars=0, max_tokens=0) is True

    def test_exceeds_token_budget(self):
        # Long text with many tokens should exceed a budget of 1
        text = "word " * 30
        assert _meets_budget(text, max_chars=None, max_tokens=1) is False


class TestNormalizeFenceBoundaries:
    def test_fence_at_line_start_is_unchanged(self):
        text = "intro\n```python\ncode\n```\n"
        assert _normalize_fence_boundaries(text) == text

    def test_fence_after_inline_text_gets_newline_inserted(self):
        text = "intro```python\ncode\n```\n"
        result = _normalize_fence_boundaries(text)
        assert "intro\n```python\n" in result

    def test_crlf_normalized_to_lf(self):
        text = "intro\r\n```python\r\ncode\r\n```\r\n"
        result = _normalize_fence_boundaries(text)
        assert "\r\n" not in result


class TestSplitFencedCode:
    def test_plain_text_returns_single_text_part(self):
        parts = _split_fenced_code("Hello world")
        assert parts == [("text", "Hello world")]

    def test_fenced_block_produces_code_and_text_parts(self):
        text = "Before\n```\ncode\n```\nAfter\n"
        parts = _split_fenced_code(text)
        kinds = [k for k, _ in parts]
        assert "code" in kinds
        assert "text" in kinds

    def test_code_block_content_is_preserved_verbatim(self):
        text = "```\nx = 1\n```\n"
        parts = _split_fenced_code(text)
        code_chunks = [c for k, c in parts if k == "code"]
        assert any("x = 1" in c for c in code_chunks)

    def test_unclosed_fence_flushed_as_code(self):
        text = "```\nunclosed code"
        parts = _split_fenced_code(text)
        kinds = [k for k, _ in parts]
        assert "code" in kinds

    def test_empty_string_returns_empty_list(self):
        assert _split_fenced_code("") == []


class TestNormalizeLine:
    def test_indented_code_block_unchanged(self):
        line = "    indented code block"
        assert _normalize_line(line, level=1) == line

    def test_table_row_unchanged(self):
        line = "| col1 | col2 | col3 |"
        assert _normalize_line(line, level=1) == line

    def test_multiple_internal_spaces_collapsed(self):
        line = "word1    word2    word3"
        result = _normalize_line(line, level=1)
        assert "  " not in result
        assert "word1" in result and "word3" in result

    def test_list_marker_rest_spaces_normalized(self):
        line = "- item   with   extra   spaces"
        result = _normalize_line(line, level=1)
        assert "  " not in result
        assert result.startswith("- ")

    def test_tab_indented_line_unchanged(self):
        line = "\tsome code"
        assert _normalize_line(line, level=1) == line


class TestOptimizeText:
    def test_empty_text_returns_empty_with_zero_chars(self):
        out, stats = optimize_text("")
        assert out == ""
        assert stats.before_chars == 0

    def test_stats_is_optimize_stats_instance(self):
        _, stats = optimize_text("Hello world")
        assert isinstance(stats, OptimizeStats)

    def test_stats_before_chars_matches_input_length(self):
        text = "Hello world"
        _, stats = optimize_text(text)
        assert stats.before_chars == len(text)

    def test_clean_text_not_changed(self):
        text = "Clean sentence with no extra whitespace."
        out, stats = optimize_text(text)
        assert not stats.changed

    def test_consecutive_duplicate_lines_deduplicated(self):
        text = "Hello\nHello\nWorld"
        out, _ = optimize_text(text)
        lines = [line for line in out.split("\n") if line.strip()]
        assert lines.count("Hello") == 1

    def test_multiple_blank_lines_collapsed(self):
        text = "Line one\n\n\n\nLine two"
        out, _ = optimize_text(text)
        assert "\n\n\n" not in out

    def test_code_block_content_preserved(self):
        text = "Before\n```python\nx = 1\ny = 2\n```\nAfter"
        out, _ = optimize_text(text)
        assert "x = 1" in out
        assert "y = 2" in out

    def test_no_budget_always_reports_met(self):
        _, stats = optimize_text("a" * 5000)
        assert stats.met_max_chars is True
        assert stats.met_max_tokens is True

    def test_char_budget_satisfied_for_short_text(self):
        _, stats = optimize_text("Short text.", max_chars=1000)
        assert stats.met_max_chars is True

    def test_after_chars_lte_before_chars(self):
        # Optimizer only removes content; never adds.
        text = "Word   with   spaces\n\nBlank\n\nLines"
        _, stats = optimize_text(text)
        assert stats.after_chars <= stats.before_chars
