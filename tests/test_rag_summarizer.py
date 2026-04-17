from unittest.mock import MagicMock, patch
from app.rag.summarizer import (
    count_tokens_approx,
    summarize_document,
    summarize_for_ingest,
    _get_client,
)
from app.llm_engine.client import WorkerClient


def test_count_tokens_approx():
    # Test text length fallback estimation (assuming tiktoken isn't forced or we just test the math)
    text = "Hello world"
    # the fallback divides length by ratio (4.0) -> len(11) / 4 = 2
    # if tiktoken is installed, it uses that instead. We can just check it returns an int > 0
    count = count_tokens_approx(text)
    assert isinstance(count, int)
    assert count > 0


def test_summarize_document_empty():
    assert summarize_document("") == ""
    assert summarize_document("   ") == ""
    assert summarize_document(None) == ""


def test_summarize_document_short_text():
    short_text = "This is short."
    # With max_tokens=500, this should skip summarization
    result = summarize_document(short_text, max_tokens=500)
    assert result == short_text


def test_summarize_document_long_text_success():
    long_text = "word " * 1000
    mock_client = MagicMock(spec=WorkerClient)
    mock_client._call_api.return_value = "Mocked summary"

    result = summarize_document(long_text, max_tokens=10, client=mock_client)
    assert result == "Mocked summary"
    mock_client._call_api.assert_called_once()


def test_summarize_document_long_text_fallback():
    long_text = "word " * 1000
    mock_client = MagicMock(spec=WorkerClient)
    mock_client._call_api.side_effect = Exception("LLM Error")

    result = summarize_document(long_text, max_tokens=5, client=mock_client)
    # The fallback splits by words and takes max_tokens words, then appends "..."
    # "word " * 1000 -> split is ["word", "word", ...]
    # max_tokens=5 -> 5 words -> "word word word word word..."
    assert result == "word word word word word..."


def test_summarize_for_ingest():
    long_text = "word " * 1000
    mock_client = MagicMock(spec=WorkerClient)
    mock_client._call_api.return_value = "Mocked ingest summary"

    result = summarize_for_ingest(long_text, max_tokens=10, client=mock_client)
    assert result == "Mocked ingest summary"
    mock_client._call_api.assert_called_once()


def test_get_client():
    client1 = _get_client()
    client2 = _get_client()
    assert client1 is client2
    assert isinstance(client1, WorkerClient)


def test_count_tokens_approx_import_error():
    # Force ImportError for tiktoken to hit lines 49-50
    with patch.dict("sys.modules", {"tiktoken": None}):
        # Need to ensure _tiktoken_enc is None
        with patch("app.rag.summarizer._tiktoken_enc", None):
            text = "Hello world"
            # Since tiktoken is missing, we use fallback len(text)/4.0 -> len(11)/4.0 -> 2
            count = count_tokens_approx(text)
            assert count == 2
