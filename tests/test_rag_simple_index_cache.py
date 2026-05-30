import pytest
from app.rag.simple_index import _query_cache, _clear_query_cache, _cache_put, _cache_get

def test_clear_query_cache():
    # Setup: populate the cache
    _cache_put("test_key", [{"mock": "data"}])
    assert "test_key" in _query_cache
    assert _cache_get("test_key") == [{"mock": "data"}]
    assert len(_query_cache) > 0

    # Action: clear the cache
    _clear_query_cache()

    # Verify: cache is empty
    assert len(_query_cache) == 0
    assert _cache_get("test_key") is None
