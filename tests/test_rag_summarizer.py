from unittest.mock import MagicMock

from app.rag.summarizer import summarize_document


def test_summarize_document_short_text():
    """Test that short text is returned directly without calling the LLM."""
    mock_client = MagicMock()
    text = "Short text."

    # max_tokens=100 is way bigger than the length of the text.
    result = summarize_document(text, max_tokens=100, client=mock_client)

    assert result == text
    mock_client._call_api.assert_not_called()


def test_summarize_document_happy_path():
    """Test that a successful LLM call returns the summary."""
    mock_client = MagicMock()
    # Mock the LLM returning a summary.
    mock_client._call_api.return_value = " This is a summary.  "

    # Text must be long enough to bypass the short text check.
    text = "word " * 50
    result = summarize_document(text, max_tokens=5, client=mock_client)

    assert result == "This is a summary."
    mock_client._call_api.assert_called_once()


def test_summarize_document_error_fallback():
    """Test the fallback logic when the LLM client raises an exception."""
    mock_client = MagicMock()
    mock_client._call_api.side_effect = Exception("Simulated LLM failure")

    text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"

    # For a string "word1 ... word10", max_tokens=5.
    result = summarize_document(text, max_tokens=5, client=mock_client)

    # The fallback splits by words and takes the first `max_tokens` words, then adds "..."
    assert result == "word1 word2 word3 word4 word5..."
