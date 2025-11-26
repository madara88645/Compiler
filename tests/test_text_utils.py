from app.text_utils import compress_text_block, estimate_tokens


def test_estimate_tokens_simple():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 1


def test_compress_text_block_sentences():
    text = "Sentence one. Sentence two is longer. Sentence three also exists."
    shortened = compress_text_block(text, max_chars=25)
    assert len(shortened) <= 28
    assert shortened.endswith("…")


def test_compress_text_block_plain_slice():
    text = "x" * 100
    result = compress_text_block(text, max_chars=10)
    assert result.startswith("x") and result.endswith("…")
    assert len(result) <= 11
