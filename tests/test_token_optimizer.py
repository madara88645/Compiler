from app.text_utils import estimate_tokens
from app.token_optimizer import optimize_text


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
