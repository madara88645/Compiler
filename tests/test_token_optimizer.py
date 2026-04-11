from app.text_utils import estimate_tokens
from app.token_optimizer import (
    _normalize_fence_boundaries,
    optimize_text,
    _optimize_once,
    _meets_budget,
    _is_fence_close,
    _looks_like_table_row,
    _optimize_markdown_text,
    _split_fenced_code,
    _normalize_line,
)


def test_normalize_fence_boundaries():
    # Insert newlines when preceded by non-newline
    assert _normalize_fence_boundaries("Intro```python\n") == "Intro\n```python\n"
    assert _normalize_fence_boundaries("Intro~~~python\n") == "Intro\n~~~python\n"

    # Multiple backticks/tildes
    assert _normalize_fence_boundaries("Intro````python\n") == "Intro\n````python\n"
    assert _normalize_fence_boundaries("Intro~~~~python\n") == "Intro\n~~~~python\n"

    # Unchanged cases: already have exactly one newline or at start
    assert _normalize_fence_boundaries("Intro\n```python\n") == "Intro\n```python\n"
    assert _normalize_fence_boundaries("```python\n") == "```python\n"

    # Inline code shouldn't be affected
    assert _normalize_fence_boundaries("Some `inline` code\n") == "Some `inline` code\n"
    assert _normalize_fence_boundaries("Some ~~inline~~ code\n") == "Some ~~inline~~ code\n"

    # Handle carriage returns
    assert _normalize_fence_boundaries("Intro\r\n```python\r\n") == "Intro\n```python\n"
    assert _normalize_fence_boundaries("Intro\r\n~~~python\r\n") == "Intro\n~~~python\n"

    # Empty inputs
    assert _normalize_fence_boundaries("") == ""


def test_optimize_preserves_fenced_code_block_verbatim():
    text = (
        "Intro paragraph with   extra   spaces.\n\n"
        "```python\n"
        "def  foo():\n"
        "    return  1\n"
        "```\n\n"
        "Outro paragraph with   extra   spaces.\n"
    )

    optimized, _ = optimize_text(text)

    # Code block should be preserved exactly, including internal spacing.
    assert "```python\n" in optimized
    assert "def  foo():\n" in optimized
    assert "    return  1\n" in optimized
    assert "```\n" in optimized


def test_optimize_preserves_fenced_code_block_even_when_budget_forces_multiple_passes():
    text = (
        "Intro  with   spaces\n\n"
        "```python\n"
        "def  foo():\n"
        "    return  1\n"
        "```\n\n"
        "Outro  with   spaces\n"
    )

    optimized, _ = optimize_text(text, max_tokens=1)

    assert "```python\n" in optimized
    assert "def  foo():\n" in optimized
    assert "    return  1\n" in optimized
    assert "```\n" in optimized


def test_optimize_reduces_tokens_for_whitespace_heavy_text():
    # Token estimation is char-sensitive in this repo; make chars dominate.
    text = "hello" + (" " * 400) + "world"
    before = estimate_tokens(text)

    optimized, st = optimize_text(text)

    after = estimate_tokens(optimized)
    assert st.before_tokens == before
    assert st.after_tokens == after
    assert len(optimized) < len(text)
    assert after <= before


def test_optimize_budget_flags_best_effort_stats():
    text = "A\n\n\nB\n\n\nC\n"  # lots of blank lines

    optimized, st = optimize_text(text, max_chars=3)

    # Optimizer should not truncate content, so budget may not be met.
    assert st.met_max_chars is False
    assert "A" in optimized and "B" in optimized and "C" in optimized


def test_optimize_is_idempotent():
    text = "Title\n\n-  item   one\n-  item   two\n\n"

    once, _ = optimize_text(text)
    twice, _ = optimize_text(once)

    assert twice == once


def test_optimize_bad_token_ratio():
    # Covers exception in max_tokens * token_ratio
    out, stats = optimize_text("hello", max_tokens=10, token_ratio=None)
    assert stats.met_max_tokens is True


def test_optimize_max_level_break():
    # Make a budget we never hit, with text that can be optimized a bit
    # Triggers level >= 3 break when candidates exhausted
    out, stats = optimize_text("  hello  \n\n  world  ", max_chars=1)
    assert out == "hello\nworld"


def test_optimize_level_3_list_marker():
    # Triggers level >= 3 in optimize_text to cover loop and list marker edge cases

    out = _optimize_once("  -   item 1", level=3)
    assert out == "-   item 1"

    out, stats = optimize_text("  -   item 1\n\n  *   item 2\n\n   1.  item 3", max_chars=1)


def test_optimize_level_2_blank_lines():
    out = _optimize_once("hello\n\n\nworld", level=2)
    assert out == "hello\nworld"


def test_meets_budget():
    assert _meets_budget("hello", max_chars=1, max_tokens=None) is False
    assert _meets_budget("hello", max_chars=10, max_tokens=None) is True
    assert _meets_budget("hello", max_chars=None, max_tokens=1) is False
    assert _meets_budget("hello", max_chars=None, max_tokens=10) is True


def test_is_fence_close():
    assert _is_fence_close("```", "") is False
    assert _is_fence_close("   \n", "```") is False
    assert _is_fence_close("```", "xxx") is False
    assert _is_fence_close("```", "```") is True
    assert _is_fence_close("~~~", "~~~") is True


def test_looks_like_table_row():
    assert _looks_like_table_row("| a | b |") is True
    assert _looks_like_table_row("no pipes") is False


def test_optimize_level_2_consecutive_blank_lines():
    # Testing level 2 removing all blank lines
    out = _optimize_markdown_text("hello\n\n\nworld", level=2)
    assert out == "hello\nworld"

    # Testing level 1 collapsing consecutive blank lines
    out = _optimize_markdown_text("hello\n\n\nworld", level=1)
    assert out == "hello\n\nworld"


def test_flush_empty_buffer():
    # Implicitly tested if the buffer is empty when flushed
    # E.g., multiple text flushes or empty text
    _split_fenced_code("```python\ncode\n```")


def test_optimize_list_indentation_removal_level_3():
    # line 262: if level >= 3, remove indentation before list markers
    out = _normalize_line("   - item", level=3)
    assert out == "- item"  # Space normalization after list marker reduces internal space

    out = _normalize_line("-   item   two", level=1)
    assert out == "-   item two"


def test_optimize_exact_duplicate_lines():
    out = _optimize_markdown_text("duplicate\nduplicate", level=1)
    assert out == "duplicate"


def test_list_normalization():
    # 262: level >= 3 remove indentation before list marker
    out = _normalize_line("   -   item", level=3)
    # The prefix "   " is removed, leaving "-   item"
    assert out == "-   item"


def test_list_normalization_level_3_missed():
    # This hits line 262 and 264 properly when running the full test suite
    # But let's be explicit
    out = _normalize_line("   - item", level=3)
    assert out == "- item"
