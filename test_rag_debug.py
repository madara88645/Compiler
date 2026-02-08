from app.rag.simple_index import pack


def test_pack_budget():
    results = [{"content": "test", "score": 0.9, "metadata": {}}]
    packed = pack("test query", results, max_chars=50)
    packed = pack("test query", results, max_chars=50)
    assert len(packed["included"]) >= 1
