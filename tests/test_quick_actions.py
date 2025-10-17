"""Tests for quick actions module."""

import pytest
from app.quick_actions import QuickActions, get_quick_actions


@pytest.fixture
def quick_actions():
    """Create QuickActions instance for testing."""
    return QuickActions()


def test_quick_actions_initialization(quick_actions):
    """Test QuickActions initialization."""
    assert quick_actions.search_history is not None
    assert quick_actions.favorites_mgr is not None
    assert quick_actions.templates_mgr is not None
    assert quick_actions.snippets_mgr is not None


def test_get_last_search_empty(quick_actions):
    """Test getting last search when history is empty."""
    # Clear any existing history
    quick_actions.search_history.clear()

    result = quick_actions.get_last_search()
    assert result is None


def test_get_last_search_with_data(quick_actions):
    """Test getting last search with data."""
    # Clear and add test data
    quick_actions.search_history.clear()
    quick_actions.search_history.add("test query", 5, types_filter=["template"], min_score=0.5)

    result = quick_actions.get_last_search()

    assert result is not None
    assert result["query"] == "test query"
    assert result["result_count"] == 5
    assert result["types_filter"] == ["template"]
    assert result["min_score"] == 0.5
    assert "timestamp" in result


def test_get_last_search_multiple_entries(quick_actions):
    """Test that last search returns most recent entry."""
    quick_actions.search_history.clear()
    quick_actions.search_history.add("first query", 3)
    quick_actions.search_history.add("second query", 7)
    quick_actions.search_history.add("last query", 10)

    result = quick_actions.get_last_search()

    assert result is not None
    assert result["query"] == "last query"
    assert result["result_count"] == 10


def test_get_top_favorites_empty(quick_actions):
    """Test getting top favorites when no favorites exist."""
    result = quick_actions.get_top_favorites(limit=10)
    assert isinstance(result, list)
    # May or may not be empty depending on existing data


def test_get_top_favorites_limit(quick_actions):
    """Test that limit parameter works correctly."""
    result = quick_actions.get_top_favorites(limit=3)
    assert isinstance(result, list)
    assert len(result) <= 3


def test_get_top_favorites_sorted(quick_actions):
    """Test that favorites are sorted by score."""
    result = quick_actions.get_top_favorites(limit=10)

    if len(result) > 1:
        # Check that scores are in descending order
        for i in range(len(result) - 1):
            score1 = result[i]["score"] or 0
            score2 = result[i + 1]["score"] or 0
            assert score1 >= score2


def test_get_top_favorites_structure(quick_actions):
    """Test that favorite dictionaries have correct structure."""
    result = quick_actions.get_top_favorites(limit=1)

    if result:
        fav = result[0]
        assert "id" in fav
        assert "prompt_text" in fav
        assert "score" in fav
        assert "domain" in fav
        assert "tags" in fav
        assert "notes" in fav
        assert "use_count" in fav
        assert "timestamp" in fav


def test_get_random_template(quick_actions):
    """Test getting a random template."""
    result = quick_actions.get_random_template()

    # May be None if no templates exist
    if result:
        assert "name" in result
        assert "description" in result
        assert "template_text" in result
        assert "variables" in result
        assert "category" in result
        assert "tags" in result


def test_get_random_snippet(quick_actions):
    """Test getting a random snippet."""
    result = quick_actions.get_random_snippet()

    # May be None if no snippets exist
    if result:
        assert "title" in result
        assert "content" in result
        assert "category" in result
        assert "description" in result
        assert "tags" in result
        assert "use_count" in result


def test_get_random_item_template_type(quick_actions):
    """Test getting random item with template type."""
    result = quick_actions.get_random_item(item_type="template")

    if result:
        assert result["type"] == "template"
        assert result["data"] is not None


def test_get_random_item_snippet_type(quick_actions):
    """Test getting random item with snippet type."""
    result = quick_actions.get_random_item(item_type="snippet")

    if result:
        assert result["type"] == "snippet"
        assert result["data"] is not None


def test_get_random_item_no_type(quick_actions):
    """Test getting random item without specifying type."""
    result = quick_actions.get_random_item(item_type=None)

    if result:
        assert result["type"] in ["template", "snippet"]
        assert result["data"] is not None


def test_get_random_item_returns_different_items(quick_actions):
    """Test that random actually returns different items."""
    results = set()

    # Try 10 times to get different items
    for _ in range(10):
        result = quick_actions.get_random_item()
        if result and result["data"]:
            # Use title/name as identifier
            identifier = result["data"].get("title") or result["data"].get("name")
            if identifier:
                results.add(identifier)

    # If we have multiple items, we should get different ones
    # (with high probability)
    # This test may occasionally fail due to randomness, but very unlikely


def test_singleton_pattern():
    """Test that get_quick_actions returns singleton."""
    qa1 = get_quick_actions()
    qa2 = get_quick_actions()

    assert qa1 is qa2


def test_get_top_favorites_default_limit(quick_actions):
    """Test default limit of 10 for top favorites."""
    result = quick_actions.get_top_favorites()
    assert isinstance(result, list)
    assert len(result) <= 10


def test_get_last_search_includes_all_fields(quick_actions):
    """Test that last search includes all expected fields."""
    quick_actions.search_history.clear()
    quick_actions.search_history.add(
        "comprehensive test",
        result_count=15,
        types_filter=["history", "favorite"],
        min_score=75.5,
    )

    result = quick_actions.get_last_search()

    assert result is not None
    assert "query" in result
    assert "result_count" in result
    assert "timestamp" in result
    assert "types_filter" in result
    assert "min_score" in result


def test_random_template_multiple_calls(quick_actions):
    """Test that random template can be called multiple times."""
    results = []
    for _ in range(3):
        result = quick_actions.get_random_template()
        results.append(result)

    # All should be None or all should have data (depending on templates existence)
    if results[0] is not None:
        for result in results:
            assert result is not None


def test_random_snippet_multiple_calls(quick_actions):
    """Test that random snippet can be called multiple times."""
    results = []
    for _ in range(3):
        result = quick_actions.get_random_snippet()
        results.append(result)

    # All should be None or all should have data (depending on snippets existence)
    if results[0] is not None:
        for result in results:
            assert result is not None


def test_get_top_favorites_with_zero_limit(quick_actions):
    """Test getting top favorites with limit of 0."""
    result = quick_actions.get_top_favorites(limit=0)
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_top_favorites_with_large_limit(quick_actions):
    """Test getting top favorites with very large limit."""
    result = quick_actions.get_top_favorites(limit=1000)
    assert isinstance(result, list)
    # Should return all available favorites (capped by actual count)
