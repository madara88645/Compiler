"""Unit tests for app.text_utils — pure token estimation and text compression."""
from __future__ import annotations

import pytest

from app.text_utils import compress_text_block, estimate_tokens


class TestEstimateTokens:
    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_minimum_is_one_for_any_nonempty_text(self):
        # single char: chars=1, words=1; min(0.25, 1.33)=0.25 → ceil=1 → max(1,1)=1
        assert estimate_tokens("a") == 1

    def test_single_word_returns_one(self):
        # "test": chars=4, words=1; min(4/4, 1/0.75)=min(1.0,1.33)=1.0 → ceil=1
        assert estimate_tokens("test") == 1

    def test_chars_path_for_long_single_word(self):
        # "abcdefghijklmnopqrstuvwxyz": chars=26, words=1
        # min(26/4, 1/0.75) = min(6.5, 1.33) = 1.33 → ceil=2
        assert estimate_tokens("abcdefghijklmnopqrstuvwxyz") == 2

    def test_typical_english_sentence(self):
        # "The quick brown fox": chars=19, words=4
        # min(19/4, 4/0.75) = min(4.75, 5.33) = 4.75 → ceil=5
        assert estimate_tokens("The quick brown fox") == 5

    def test_short_words_chars_path_dominates(self):
        # "a b c d": chars=7, words=4; min(7/4, 4/0.75)=min(1.75,5.33)=1.75 → ceil=2
        assert estimate_tokens("a b c d") == 2

    def test_scales_with_text_length(self):
        short_tokens = estimate_tokens("short")
        long_tokens = estimate_tokens("a " * 100)
        assert long_tokens > short_tokens

    def test_result_is_integer(self):
        assert isinstance(estimate_tokens("Hello world"), int)


class TestCompressTextBlock:
    def test_empty_string_returns_empty(self):
        assert compress_text_block("") == ""

    def test_none_treated_as_empty(self):
        assert compress_text_block(None) == ""  # type: ignore[arg-type]

    def test_short_text_within_limit_unchanged(self):
        text = "Short sentence."
        assert compress_text_block(text, max_chars=600) == text

    def test_text_at_exact_limit_unchanged(self):
        text = "x" * 100
        assert compress_text_block(text, max_chars=100) == text

    def test_default_limit_is_600(self):
        text = "This is short."
        assert compress_text_block(text) == text

    def test_single_long_sentence_truncated_with_ellipsis(self):
        text = "a" * 200
        result = compress_text_block(text, max_chars=100)
        assert result.endswith("…")
        assert len(result) <= 102

    def test_multi_sentence_greedy_kept_within_limit(self):
        # First sentence fits; second does not.
        text = "First sentence. " + "B" * 100 + "."
        result = compress_text_block(text, max_chars=20)
        assert "First sentence" in result
        assert result.endswith("…")

    def test_compressed_result_ends_with_ellipsis_when_truncated(self):
        sentences = ". ".join(["Sentence number {}".format(i) for i in range(20)])
        result = compress_text_block(sentences, max_chars=50)
        assert result.endswith("…")

    def test_leading_trailing_whitespace_stripped(self):
        text = "   Short text.   "
        result = compress_text_block(text, max_chars=600)
        assert result == "Short text."

    def test_no_ellipsis_when_text_fits(self):
        text = "Just right."
        result = compress_text_block(text, max_chars=600)
        assert not result.endswith("…")
