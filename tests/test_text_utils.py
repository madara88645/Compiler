"""Tests for pure functions in app.text_utils and app.token_optimizer.

All functions covered are deterministic with no external I/O, network, or DB
dependencies. They were previously at 0% coverage.
"""

from app.text_utils import compress_text_block, estimate_tokens
from app.token_optimizer import (
    OptimizeStats,
    _is_fence_close,
    _looks_like_table_row,
    _meets_budget,
    _normalize_fence_boundaries,
    _split_fenced_code,
    optimize_text,
)


class TestEstimateTokens:
    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_single_word_returns_at_least_one(self):
        assert estimate_tokens("hello") >= 1

    def test_four_char_word(self):
        # "test" = 4 chars/4 = 1.0; 1 word/0.75 = 1.33 -> min = 1.0 -> ceil = 1
        assert estimate_tokens("test") == 1

    def test_result_always_positive_for_nonempty(self):
        for text in ["a", "ab", "hello world", "x" * 100]:
            assert estimate_tokens(text) >= 1

    def test_longer_text_produces_more_tokens(self):
        short = estimate_tokens("hello")
        long = estimate_tokens("hello " * 50)
        assert long > short

    def test_whitespace_only_returns_at_least_one(self):
        # "   " -> 3 chars/4 = 0.75, 0 words -> min(0.75, 0) = 0 -> max(1, ceil(0)) = 1
        assert estimate_tokens("   ") >= 1


class TestCompressTextBlock:
    def test_short_text_returned_unchanged(self):
        text = "Short text."
        assert compress_text_block(text, max_chars=100) == text

    def test_text_at_exact_limit_unchanged(self):
        text = "a" * 600
        assert compress_text_block(text) == text

    def test_long_single_block_truncated_with_ellipsis(self):
        text = "a" * 700
        result = compress_text_block(text, max_chars=10)
        assert result.endswith("…")
        assert len(result) <= 12

    def test_empty_string_returns_empty(self):
        assert compress_text_block("") == ""

    def test_whitespace_only_returns_empty(self):
        assert compress_text_block("   ") == ""

    def test_result_shorter_than_input_when_truncated(self):
        long_text = "Word. " * 200
        result = compress_text_block(long_text, max_chars=50)
        assert len(result) < len(long_text)

    def test_first_sentence_kept_across_sentence_boundary(self):
        text = "First sentence. Second sentence that is much longer."
        result = compress_text_block(text, max_chars=25)
        assert "First sentence" in result

    def test_custom_max_chars_limits_output(self):
        text = "Hello world. This is a test sentence. Another one here."
        result = compress_text_block(text, max_chars=20)
        assert len(result) <= 22  # 20 + len("…")


class TestMeetsBudget:
    def test_no_budget_always_true(self):
        assert _meets_budget("any text", max_chars=None, max_tokens=None) is True

    def test_within_char_budget(self):
        assert _meets_budget("hello", max_chars=10, max_tokens=None) is True

    def test_exceeds_char_budget(self):
        assert _meets_budget("hello world", max_chars=5, max_tokens=None) is False

    def test_within_token_budget(self):
        assert _meets_budget("hi", max_chars=None, max_tokens=100) is True

    def test_char_budget_fails_even_when_token_budget_passes(self):
        assert _meets_budget("hello world", max_chars=3, max_tokens=100) is False

    def test_both_budgets_satisfied(self):
        assert _meets_budget("hi", max_chars=100, max_tokens=100) is True


class TestIsFenceClose:
    def test_matching_triple_backtick(self):
        assert _is_fence_close("```\n", "```") is True

    def test_matching_quadruple_backtick(self):
        assert _is_fence_close("````\n", "````") is True

    def test_matching_tilde_fence(self):
        assert _is_fence_close("~~~\n", "~~~") is True

    def test_empty_marker_returns_false(self):
        assert _is_fence_close("```\n", "") is False

    def test_fence_open_with_lang_spec_not_close(self):
        assert _is_fence_close("```python\n", "```") is False

    def test_empty_line_returns_false(self):
        assert _is_fence_close("", "```") is False

    def test_whitespace_only_returns_false(self):
        assert _is_fence_close("   \n", "```") is False

    def test_shorter_fence_cannot_close_longer_marker(self):
        assert _is_fence_close("```\n", "````") is False

    def test_mismatched_fence_char_returns_false(self):
        assert _is_fence_close("~~~\n", "```") is False


class TestLooksLikeTableRow:
    def test_two_pipe_table_row(self):
        assert _looks_like_table_row("| col1 | col2 |") is True

    def test_three_pipe_row(self):
        assert _looks_like_table_row("| a | b | c |") is True

    def test_separator_row(self):
        assert _looks_like_table_row("|---|---|") is True

    def test_one_pipe_not_a_table(self):
        assert _looks_like_table_row("echo hello | grep hi") is False

    def test_no_pipe_not_a_table(self):
        assert _looks_like_table_row("normal text line") is False


class TestNormalizeFenceBoundaries:
    def test_fence_on_own_line_unchanged(self):
        text = "paragraph\n```python\ncode\n```\n"
        result = _normalize_fence_boundaries(text)
        assert "paragraph\n```python\n" in result

    def test_fence_merged_into_prior_line_gets_split(self):
        text = "Intro```python\ncode\n```\n"
        result = _normalize_fence_boundaries(text)
        assert "Intro\n```python\n" in result

    def test_empty_string_unchanged(self):
        assert _normalize_fence_boundaries("") == ""

    def test_crlf_converted_to_lf(self):
        text = "line\r\n```\r\ncode\r\n```\r\n"
        result = _normalize_fence_boundaries(text)
        assert "\r\n" not in result


class TestSplitFencedCode:
    def test_plain_text_returns_only_text_chunks(self):
        text = "plain text\nno fences\n"
        parts = _split_fenced_code(text)
        assert all(k == "text" for k, _ in parts)
        assert "plain text" in "".join(c for _, c in parts)

    def test_fenced_block_produces_text_and_code_kinds(self):
        text = "before\n```\ncode here\n```\nafter\n"
        parts = _split_fenced_code(text)
        kinds = [k for k, _ in parts]
        assert "text" in kinds
        assert "code" in kinds

    def test_code_content_preserved_verbatim(self):
        text = "intro\n```python\nprint('hello')\n```\noutro\n"
        parts = _split_fenced_code(text)
        code_chunks = [c for k, c in parts if k == "code"]
        assert any("print('hello')" in c for c in code_chunks)

    def test_unclosed_fence_classified_as_code(self):
        text = "text\n```\nunclosed code\n"
        parts = _split_fenced_code(text)
        kinds = [k for k, _ in parts]
        assert "code" in kinds

    def test_tilde_fence_works(self):
        text = "before\n~~~\ncode\n~~~\nafter\n"
        parts = _split_fenced_code(text)
        kinds = [k for k, _ in parts]
        assert "code" in kinds

    def test_empty_string_returns_no_content(self):
        parts = _split_fenced_code("")
        assert parts == [] or all(c == "" for _, c in parts)


class TestOptimizeText:
    def test_empty_text_returns_empty_string(self):
        result, _ = optimize_text("")
        assert result == ""

    def test_returns_optimize_stats_dataclass(self):
        _, stats = optimize_text("some text")
        assert isinstance(stats, OptimizeStats)

    def test_stats_before_chars_matches_input_length(self):
        text = "hello world"
        _, stats = optimize_text(text)
        assert stats.before_chars == len(text)

    def test_stats_after_chars_matches_output_length(self):
        text = "hello world"
        result, stats = optimize_text(text)
        assert stats.after_chars == len(result)

    def test_fenced_code_preserved_through_optimization(self):
        text = "intro\n```python\nprint('x')\nprint('y')\n```\noutro\n"
        result, _ = optimize_text(text)
        assert "print('x')" in result
        assert "print('y')" in result

    def test_trailing_blank_lines_collapsed(self):
        text = "content\n\n\n"
        result, _ = optimize_text(text)
        assert not result.endswith("\n\n")

    def test_optimization_never_increases_output_size(self):
        text = "word " * 200
        _, stats = optimize_text(text, max_chars=100)
        assert stats.after_chars <= stats.before_chars

    def test_changed_flag_set_when_output_differs(self):
        # Multiple blank lines should be collapsed (level >= 2 removes blank lines)
        text = "line\n\n\nline\n"
        _, stats = optimize_text(text)
        if stats.before_chars != stats.after_chars:
            assert stats.changed is True
