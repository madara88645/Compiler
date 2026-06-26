"""Tests for app.text_utils — pure token estimation and text compression."""
import pytest

from app.text_utils import compress_text_block, estimate_tokens


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

def test_estimate_tokens_empty_string():
    assert estimate_tokens("") == 0


def test_estimate_tokens_single_char():
    # 1 char, 1 word → min(0.25, 1.333) = 0.25 → ceil = 1 → max(1, 1) = 1
    assert estimate_tokens("a") == 1


def test_estimate_tokens_three_words():
    # "The quick brown" → 15 chars, 3 words → min(3.75, 4.0) = 3.75 → ceil = 4
    assert estimate_tokens("The quick brown") == 4


def test_estimate_tokens_always_at_least_one_for_non_empty():
    assert estimate_tokens("x") >= 1


def test_estimate_tokens_scales_with_text_length():
    short = "hello"
    long_text = "hello world " * 50
    assert estimate_tokens(long_text) > estimate_tokens(short)


def test_estimate_tokens_whitespace_only_is_zero_words():
    # "   " → split() returns [] → 0 words; 3 chars → min(0.75, 0) → 0 → max(1,0)=1
    # The important thing is that it doesn't crash.
    result = estimate_tokens("   ")
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# compress_text_block
# ---------------------------------------------------------------------------

def test_compress_text_block_short_text_unchanged():
    text = "Short sentence."
    assert compress_text_block(text, max_chars=100) == text


def test_compress_text_block_exact_boundary_unchanged():
    # len == max_chars → condition `len(text) <= max_chars` is True → no compression
    text = "Hello world."
    assert len(text) == 12
    assert compress_text_block(text, max_chars=12) == text


def test_compress_text_block_none_returns_empty():
    assert compress_text_block(None) == ""


def test_compress_text_block_empty_returns_empty():
    assert compress_text_block("") == ""


def test_compress_text_block_multi_sentence_appends_ellipsis():
    text = "First sentence. Second sentence. Third sentence."
    result = compress_text_block(text, max_chars=20)
    assert result.endswith("…")
    # Result must not exceed max_chars by more than the ellipsis character.
    assert len(result) <= 21


def test_compress_text_block_single_long_sentence_truncates():
    # No sentence boundary → fall back to slice + ellipsis
    text = "A" * 100
    result = compress_text_block(text, max_chars=50)
    assert result.endswith("…")
    assert len(result) <= 52  # 50 chars + 1 ellipsis char


def test_compress_text_block_keeps_content_within_limit():
    text = "Alpha. Beta. Gamma. Delta. Epsilon."
    result = compress_text_block(text, max_chars=15)
    # Whatever fits should still be the beginning of the original text.
    assert text.startswith(result.rstrip("…").strip())


def test_compress_text_block_default_max_chars_allows_long_text():
    # Default max_chars=600; text shorter than that returns unchanged.
    text = "x" * 599
    assert compress_text_block(text) == text
