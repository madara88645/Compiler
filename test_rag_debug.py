
def test_pack_budget():
    packed = pack("test query", results, max_chars=50)
    assert len(packed["included"]) >= 1
