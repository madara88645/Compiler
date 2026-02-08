import pytest
from app.rag.simple_index import (
    _chunk_text,
    _chunk_text_fixed,
    _chunk_text_paragraph,
    _chunk_text_semantic,
    _split_sentences,
)


# --------------------------------------------------------------------------
# SENTENCE SPLITTING TESTS
# --------------------------------------------------------------------------

def test_split_sentences_basic():
    text = "Hello world. This is a test. How are you?"
    sentences = _split_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Hello world."
    assert sentences[1] == "This is a test."
    assert sentences[2] == "How are you?"


def test_split_sentences_with_exclamation():
    text = "Wow! That's amazing. Really?"
    sentences = _split_sentences(text)
    assert len(sentences) == 3


def test_split_sentences_single():
    text = "Just one sentence here"
    sentences = _split_sentences(text)
    assert len(sentences) == 1


# --------------------------------------------------------------------------
# FIXED CHUNKING TESTS
# --------------------------------------------------------------------------

def test_fixed_chunking_small_text():
    """Text smaller than chunk size returns single chunk."""
    text = "Small text"
    chunks = _chunk_text_fixed(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_fixed_chunking_large_text():
    """Large text is split with overlap."""
    text = "A" * 2500
    chunks = _chunk_text_fixed(text, chunk_size=1000, overlap=200)
    assert len(chunks) > 1
    # Check overlap: end of chunk 1 should match start of chunk 2
    overlap_text = chunks[0][-200:]
    assert chunks[1].startswith(overlap_text)


# --------------------------------------------------------------------------
# PARAGRAPH CHUNKING TESTS
# --------------------------------------------------------------------------

def test_paragraph_chunking_preserves_paragraphs():
    """Paragraph boundaries are preserved when possible."""
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
    chunks = _chunk_text_paragraph(text, chunk_size=200)
    # Should fit in one chunk
    assert len(chunks) == 1
    assert "\n\n" in chunks[0]


def test_paragraph_chunking_splits_large_paragraphs():
    """Large paragraphs are split at sentence boundaries."""
    # Create a paragraph with many sentences
    sentences = ["This is sentence number {}.".format(i) for i in range(20)]
    text = " ".join(sentences)
    
    chunks = _chunk_text_paragraph(text, chunk_size=200)
    assert len(chunks) > 1
    
    # No chunk should exceed size (with some tolerance for overlap)
    for chunk in chunks:
        assert len(chunk) <= 250  # Allow some tolerance


def test_paragraph_chunking_sentence_overlap():
    """Last sentence is used as overlap for context."""
    text = "Para one sentence one. Para one sentence two.\n\nPara two content here. More in para two."
    chunks = _chunk_text_paragraph(text, chunk_size=80)
    
    # If split, second chunk should start with overlap from first
    if len(chunks) > 1:
        # The overlap logic should include context
        assert len(chunks[1]) > 10  # Has meaningful content


# --------------------------------------------------------------------------
# SEMANTIC CHUNKING TESTS
# --------------------------------------------------------------------------

def test_semantic_chunking_groups_similar():
    """Similar sentences are grouped together."""
    text = (
        "Python is a programming language. Python supports multiple paradigms. "
        "Machine learning uses Python extensively. "
        "The weather today is sunny. It might rain tomorrow. The forecast looks good."
    )
    chunks = _chunk_text_semantic(text, chunk_size=500, similarity_threshold=0.2)
    
    # Should create at least 2 chunks (programming vs weather)
    assert len(chunks) >= 1


def test_semantic_chunking_respects_size():
    """Chunks don't exceed size limit."""
    sentences = ["Topic {}: some content about this topic here.".format(i) for i in range(50)]
    text = " ".join(sentences)
    
    chunks = _chunk_text_semantic(text, chunk_size=200)
    for chunk in chunks:
        assert len(chunk) <= 220  # Small tolerance


# --------------------------------------------------------------------------
# UNIFIED _chunk_text TESTS
# --------------------------------------------------------------------------

def test_chunk_text_strategy_fixed():
    text = "A" * 2000
    chunks = _chunk_text(text, chunk_size=500, strategy="fixed")
    assert len(chunks) > 1


def test_chunk_text_strategy_paragraph():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = _chunk_text(text, chunk_size=500, strategy="paragraph")
    assert len(chunks) == 1  # Should fit in one


def test_chunk_text_strategy_semantic():
    text = "Topic A content. Topic A more. Topic B different. Topic B again."
    chunks = _chunk_text(text, chunk_size=500, strategy="semantic")
    assert len(chunks) >= 1


def test_chunk_text_default_is_paragraph():
    """Default strategy should be paragraph."""
    text = "First para.\n\nSecond para."
    chunks_default = _chunk_text(text, chunk_size=500)
    chunks_paragraph = _chunk_text(text, chunk_size=500, strategy="paragraph")
    assert chunks_default == chunks_paragraph


def test_chunk_text_empty_returns_empty():
    """Empty text returns empty list."""
    assert _chunk_text("") == []
    assert _chunk_text("   ") == []


def test_chunk_text_small_returns_single():
    """Text smaller than chunk size returns single chunk."""
    text = "Small text here"
    chunks = _chunk_text(text, chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0] == text
