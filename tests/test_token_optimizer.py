"""Tests for app.token_optimizer — deterministic whitespace/markdown optimizer."""
import pytest

from app.token_optimizer import (
    OptimizeStats,
    _is_fence_close,
    _looks_like_table_row,
    _meets_budget,
    _normalize_fence_boundaries,
    _split_fenced_code,
    optimize_text,
)


# ---------------------------------------------------------------------------
# optimize_text (public API)
# ---------------------------------------------------------------------------

def test_optimize_text_empty_string():
    result, stats = optimize_text("")
    assert result == ""
    assert stats.before_chars == 0
    assert stats.after_chars == 0
    assert stats.changed is False


def test_optimize_text_returns_optimize_stats():
    _, stats = optimize_text("Hello world")
    assert isinstance(stats, OptimizeStats)


def test_optimize_text_before_chars_reflects_input():
    text = "Hello world"
    _, stats = optimize_text(text)
    assert stats.before_chars == len(text)


def test_optimize_text_collapses_extra_spaces():
    text = "Hello   world  foo"
    result, stats = optimize_text(text)
    assert "   " not in result
    assert stats.changed is True


def test_optimize_text_preserves_fenced_code_block_verbatim():
    # Spaces inside code blocks must not be collapsed.
    text = "Intro\n```python\nx = 1   +   2\n```\nOutro"
    result, _ = optimize_text(text)
    assert "x = 1   +   2" in result


def test_optimize_text_removes_duplicate_consecutive_lines():
    text = "line one\nline one\nline two\n"
    result, stats = optimize_text(text)
    # Duplicate "line one" should be removed.
    assert result.count("line one") == 1
    assert stats.changed is True


def test_optimize_text_after_chars_matches_result_length():
    text = "Hello   world"
    result, stats = optimize_text(text)
    assert stats.after_chars == len(result)


def test_optimize_text_met_max_chars_true_when_no_budget():
    _, stats = optimize_text("Hello world")
    assert stats.met_max_chars is True


def test_optimize_text_met_max_tokens_true_when_no_budget():
    _, stats = optimize_text("Hello world")
    assert stats.met_max_tokens is True


# ---------------------------------------------------------------------------
# _meets_budget
# ---------------------------------------------------------------------------

def test_meets_budget_no_constraints_always_true():
    assert _meets_budget("any text at all", max_chars=None, max_tokens=None) is True


def test_meets_budget_within_char_limit():
    assert _meets_budget("hello", max_chars=10, max_tokens=None) is True


def test_meets_budget_exceeds_char_limit():
    assert _meets_budget("hello world!", max_chars=5, max_tokens=None) is False


def test_meets_budget_within_token_limit():
    # "hello" → 2 tokens; limit of 5 is fine
    assert _meets_budget("hello", max_chars=None, max_tokens=5) is True


def test_meets_budget_exceeds_token_limit():
    # "hello" → 2 tokens; limit of 1 fails
    assert _meets_budget("hello", max_chars=None, max_tokens=1) is False


# ---------------------------------------------------------------------------
# _is_fence_close
# ---------------------------------------------------------------------------

def test_is_fence_close_backtick_close():
    assert _is_fence_close("```\n", "```") is True


def test_is_fence_close_tilde_close():
    assert _is_fence_close("~~~\n", "~~~") is True


def test_is_fence_close_opening_line_with_language_not_close():
    assert _is_fence_close("```python\n", "```") is False


def test_is_fence_close_empty_fence_marker():
    assert _is_fence_close("```\n", "") is False


def test_is_fence_close_blank_line_not_close():
    assert _is_fence_close("\n", "```") is False


# ---------------------------------------------------------------------------
# _looks_like_table_row
# ---------------------------------------------------------------------------

def test_looks_like_table_row_two_pipes_is_table():
    assert _looks_like_table_row("| col1 | col2 |") is True


def test_looks_like_table_row_three_pipes_is_table():
    assert _looks_like_table_row("| a | b | c |") is True


def test_looks_like_table_row_single_pipe_not_table():
    assert _looks_like_table_row("x | y") is False


def test_looks_like_table_row_plain_text_not_table():
    assert _looks_like_table_row("normal text") is False


# ---------------------------------------------------------------------------
# _split_fenced_code
# ---------------------------------------------------------------------------

def test_split_fenced_code_no_fences_returns_single_text_chunk():
    text = "plain text\nmore text"
    parts = _split_fenced_code(text)
    assert len(parts) == 1
    assert parts[0][0] == "text"
    assert "plain text" in parts[0][1]


def test_split_fenced_code_with_python_fence():
    text = "intro\n```python\ncode here\n```\noutro\n"
    parts = _split_fenced_code(text)
    kinds = [k for k, _ in parts]
    assert "code" in kinds
    assert "text" in kinds


def test_split_fenced_code_code_block_preserved_verbatim():
    code_line = "x   =   1  # spaced"
    text = f"before\n```\n{code_line}\n```\nafter\n"
    parts = _split_fenced_code(text)
    code_chunks = [c for k, c in parts if k == "code"]
    assert any(code_line in chunk for chunk in code_chunks)


def test_split_fenced_code_tilde_fence():
    text = "text\n~~~\ncode\n~~~\nmore\n"
    parts = _split_fenced_code(text)
    kinds = [k for k, _ in parts]
    assert "code" in kinds


# ---------------------------------------------------------------------------
# _normalize_fence_boundaries
# ---------------------------------------------------------------------------

def test_normalize_fence_boundaries_already_correct_no_change():
    text = "intro\n```python\ncode\n```\noutro"
    result = _normalize_fence_boundaries(text)
    # Fence must still be present.
    assert "```python" in result


def test_normalize_fence_boundaries_inserts_newline_before_fence():
    # Fence starts immediately after non-newline text.
    text = "intro```python\ncode\n```\noutro"
    result = _normalize_fence_boundaries(text)
    assert "intro\n```python" in result
