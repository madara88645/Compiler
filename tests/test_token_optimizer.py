from app.text_utils import estimate_tokens
from app.token_optimizer import _normalize_fence_boundaries, optimize_text


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


def test_derived_max_chars_exception():
    class BadRatio:
        def __float__(self):
            raise ValueError("bad ratio")

    out, stats = optimize_text("hello", max_tokens=10, token_ratio=BadRatio())
    assert stats.met_max_tokens is True


def test_meets_budget_false_cases():
    from app.token_optimizer import _meets_budget

    assert _meets_budget("hello", max_chars=2, max_tokens=None) is False
    assert _meets_budget("hello world", max_chars=None, max_tokens=1) is False


def test_optimize_budget_escalation():
    text = "hello\n\nworld"
    out, stats = optimize_text(text, max_chars=11)
    assert "\n\n" not in out

    text = "    - item1\n    - item2"
    out, stats = optimize_text(text, max_chars=5)
    assert "- item" in out


def test_is_fence_close_edge_cases():
    from app.token_optimizer import _is_fence_close

    assert _is_fence_close("```", "") is False
    assert _is_fence_close("   \n", "```") is False
    assert _is_fence_close("---", "```") is False
    assert _is_fence_close("``", "```") is False


def test_optimize_markdown_text_duplicate_lines():
    from app.token_optimizer import _optimize_markdown_text

    text = "hello\nhello\nworld"
    out = _optimize_markdown_text(text, level=1)
    assert out == "hello\nworld"


def test_normalize_line_indented_or_table():
    from app.token_optimizer import _normalize_line

    assert _normalize_line("    indented", level=1) == "    indented"
    assert _normalize_line("\tindented", level=1) == "\tindented"
    assert _normalize_line("| col1 | col2 |", level=1) == "| col1 | col2 |"


def test_looks_like_table_row():
    from app.token_optimizer import _looks_like_table_row

    assert _looks_like_table_row("| col1 | col2 |") is True
    assert _looks_like_table_row("col1 | col2") is False


def test_meets_budget_true_cases():
    from app.token_optimizer import _meets_budget

    assert _meets_budget("hello", max_chars=10, max_tokens=10) is True


def test_normalize_line_list_markers():
    from app.token_optimizer import _normalize_line

    # level 3 should strip indentation before list marker
    assert _normalize_line("  - item", level=3) == "- item"
    # Should collapse multiple spaces after list marker
    assert _normalize_line("-   item", level=1) == "-   item"
    # If the list marker doesnt match, collapse internal runs
    assert _normalize_line("word   word", level=1) == "word word"


def test_split_fenced_code_empty_buffer_flush():
    from app.token_optimizer import _split_fenced_code

    # If text starts with fence immediately, initial flush('text') has an empty buffer.
    # It shouldn't add an empty text block.
    parts = _split_fenced_code("```python\ncode\n```")
    assert parts[0][0] == "code"


def test_is_fence_close_returns_false_if_bad_marker():
    from app.token_optimizer import _is_fence_close

    assert _is_fence_close("```", "xxx") is False
