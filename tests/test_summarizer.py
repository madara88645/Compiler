from unittest import mock
import pytest

from app.rag.summarizer import count_tokens_approx


def test_count_tokens_approx_happy_path():
    """Test the happy path where tiktoken is available."""
    text = "Hello world! This is a test."
    # Reset global _tiktoken_enc to None to ensure it gets initialized in this test if available
    import app.rag.summarizer

    app.rag.summarizer._tiktoken_enc = None

    # Normally tiktoken would be imported and count would be exact
    try:
        import tiktoken

        expected_count = len(tiktoken.get_encoding("cl100k_base").encode(text))
        count = count_tokens_approx(text)
        assert count == expected_count
    except ImportError:
        pytest.skip("tiktoken not installed, skipping happy path test")


def test_count_tokens_approx_fallback():
    """Test the fallback calculation when tiktoken raises ImportError."""
    text = "Hello world! This is a test."
    ratio = 4.0
    expected_count = int(len(text) / ratio)

    # Reset global _tiktoken_enc to None
    import app.rag.summarizer

    app.rag.summarizer._tiktoken_enc = None

    # Patch sys.modules to simulate ImportError
    with mock.patch.dict("sys.modules", {"tiktoken": None}):
        count = count_tokens_approx(text, ratio=ratio)
        assert count == expected_count


def test_count_tokens_approx_fallback_custom_ratio():
    """Test the fallback calculation with a custom ratio."""
    text = "1234567890"
    ratio = 2.0
    expected_count = int(len(text) / ratio)

    # Reset global _tiktoken_enc to None
    import app.rag.summarizer

    app.rag.summarizer._tiktoken_enc = None

    with mock.patch.dict("sys.modules", {"tiktoken": None}):
        count = count_tokens_approx(text, ratio=ratio)
        assert count == expected_count
