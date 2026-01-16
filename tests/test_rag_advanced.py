
import pytest
from app.rag.simple_index import pack

def test_pack_basic_logic():
    """Verify basic packing behavior."""
    results = [
        {"path": "doc1.txt", "chunk_index": 0, "snippet": "Hello world.", "chunk_id": 1, "score": 0.9},
        {"path": "doc2.txt", "chunk_index": 0, "snippet": "Another doc.", "chunk_id": 2, "score": 0.8},
    ]
    packed = pack("test query", results, max_chars=1000)
    assert "# doc1.txt chunk=0" in packed["packed"]
    assert "Hello world." in packed["packed"]
    assert "# doc2.txt chunk=0" in packed["packed"]
    assert len(packed["included"]) == 2

def test_pack_budget():
    """Verify that packing stops when budget is exceeded."""
    results = []
    # Create 10 chunks, each ~20 chars (header adds more)
    for i in range(10):
        results.append({
            "path": f"doc{i}.txt", 
            "chunk_index": 0, 
            "snippet": f"Content for {i}.", 
            "chunk_id": i,
             "score": 0.5
        })
    
    # Very small budget, likely only 1 item fits
    packed = pack("test query", results, max_chars=50) 
    # Header is ~20 chars ("# docX.txt chunk=0\n") + content "Content for X.\n\n" (~16) = ~36 chars per block
    
    assert len(packed["included"]) >= 1
    assert len(packed["included"]) < 10

def test_pack_deduplication_placeholder():
    """Verify that we can eventually deduplicate identical content."""
    # This test is expected to fail or need adjustment once we implement dedup
    results = [
        {"path": "doc1.txt", "chunk_index": 0, "snippet": "Duplicate content.", "chunk_id": 1, "score": 0.9},
        {"path": "doc2.txt", "chunk_index": 0, "snippet": "Duplicate content.", "chunk_id": 2, "score": 0.8},
    ]
    # Current implementation does NOT dedup, so both should be there
    packed_no_dedup = pack("test query", results, dedup=False)
    assert packed_no_dedup["packed"].count("Duplicate content.") == 2
    
    # Enable dedup
    packed_dedup = pack("test query", results, dedup=True)
    assert packed_dedup["packed"].count("Duplicate content.") == 1
    assert "score=0.900" in packed_dedup["packed"] # Checks scored header

def test_pack_token_budget():
    """Verify max_tokens budget logic."""
    results = [
        {"path": "d1.txt", "chunk_index": 0, "snippet": "A" * 100, "chunk_id": 1}, # ~25 tokens
        {"path": "d2.txt", "chunk_index": 0, "snippet": "B" * 100, "chunk_id": 2}, # ~25 tokens
    ]
    # Set limit low enough to exclude second item
    # Header is roughly # d1.txt chunk=0\n (~20 chars = 5 tokens) + 25 tokens = 30 tokens
    # So max_tokens=40 should allow 1 but not 2
    packed = pack("q", results, max_tokens=40, token_chars=4.0)
    assert len(packed["included"]) == 1
    assert packed["tokens"] <= 40


