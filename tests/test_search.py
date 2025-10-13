"""Tests for smart search module."""

import pytest
from app.search import (
    SmartSearch,
    SearchResult,
    SearchResultType,
    get_search_engine,
)
from app.history import get_history_manager
from app.favorites import get_favorites_manager
from app.templates_manager import get_templates_manager
from app.snippets import get_snippets_manager
from app.collections import get_collections_manager


@pytest.fixture
def search_engine(tmp_path, monkeypatch):
    """Create a search engine with temporary storage."""
    # Create temporary managers
    history_mgr = get_history_manager()
    favorites_mgr = get_favorites_manager()
    snippets_mgr = get_snippets_manager()
    collections_mgr = get_collections_manager()

    # Clear existing data
    history_mgr.clear()
    favorites_mgr.clear()
    snippets_mgr.clear()
    collections_mgr.clear()

    # Create search engine
    engine = SmartSearch()
    return engine


@pytest.fixture
def populated_search(search_engine):
    """Create a search engine with sample data."""
    # Add history entries
    history_mgr = search_engine.history_mgr
    history_mgr.add(
        prompt_text="Teach me Python basics in 30 minutes",
        ir={"domain": "education", "language": "EN"},
        score=95.0,
    )
    history_mgr.add(
        prompt_text="Compare React vs Vue for web development",
        ir={"domain": "tech", "language": "EN"},
        score=88.5,
    )

    # Add favorites
    favorites_mgr = search_engine.favorites_mgr
    favorites_mgr.add(
        prompt_id="fav1",
        prompt_text="Write a Python function for sorting",
        tags=["python", "code"],
        domain="tech",
        score=92.0,
        notes="Best sorting example",
    )

    # Add snippets
    snippets_mgr = search_engine.snippets_mgr
    snippets_mgr.add(
        snippet_id="snip1",
        title="Python basics",
        content="Variables, loops, functions",
        category="example",
        tags=["python", "tutorial"],
    )

    # Add collections
    collections_mgr = search_engine.collections_mgr
    collections_mgr.create(
        collection_id="ml-project",
        name="Machine Learning Project",
        description="ML tutorials and examples",
        tags=["ml", "python"],
    )

    return search_engine


def test_search_result_creation():
    """Test SearchResult dataclass."""
    result = SearchResult(
        result_type=SearchResultType.HISTORY,
        id="test123",
        title="Test Title",
        content="Test content",
        score=85.5,
        metadata={"domain": "tech"},
    )

    assert result.result_type == SearchResultType.HISTORY
    assert result.id == "test123"
    assert result.title == "Test Title"
    assert result.score == 85.5


def test_search_result_to_dict():
    """Test SearchResult serialization."""
    result = SearchResult(
        result_type=SearchResultType.SNIPPET,
        id="snip1",
        title="Snippet Title",
        content="Content here",
        score=75.3,
        metadata={"tags": ["test"]},
    )

    data = result.to_dict()
    assert data["type"] == "snippet"
    assert data["id"] == "snip1"
    assert data["score"] == 75.3
    assert "metadata" in data


def test_search_engine_initialization(search_engine):
    """Test search engine initializes correctly."""
    assert search_engine.history_mgr is not None
    assert search_engine.favorites_mgr is not None
    assert search_engine.templates_mgr is not None
    assert search_engine.snippets_mgr is not None
    assert search_engine.collections_mgr is not None


def test_empty_query_returns_no_results(search_engine):
    """Test that empty query returns no results."""
    results = search_engine.search("")
    assert len(results) == 0

    results = search_engine.search("   ")
    assert len(results) == 0


def test_search_history(populated_search):
    """Test searching history entries."""
    results = populated_search.search("Python", result_types=[SearchResultType.HISTORY])

    assert len(results) > 0
    python_results = [r for r in results if "Python" in r.content or "python" in r.content.lower()]
    assert len(python_results) > 0
    assert all(r.result_type == SearchResultType.HISTORY for r in results)


def test_search_favorites(populated_search):
    """Test searching favorite entries."""
    results = populated_search.search("sorting", result_types=[SearchResultType.FAVORITE])

    assert len(results) > 0
    assert results[0].result_type == SearchResultType.FAVORITE
    assert "sorting" in results[0].content.lower()


def test_search_snippets(populated_search):
    """Test searching snippets."""
    results = populated_search.search("Python basics", result_types=[SearchResultType.SNIPPET])

    assert len(results) > 0
    assert results[0].result_type == SearchResultType.SNIPPET
    assert "python" in results[0].title.lower() or "python" in results[0].content.lower()


def test_search_collections(populated_search):
    """Test searching collections."""
    results = populated_search.search(
        "Machine Learning", result_types=[SearchResultType.COLLECTION]
    )

    assert len(results) > 0
    assert results[0].result_type == SearchResultType.COLLECTION
    assert "machine learning" in results[0].title.lower()


def test_search_all_types(populated_search):
    """Test searching across all types."""
    results = populated_search.search("Python")

    # Should have results from multiple sources
    result_types = {r.result_type for r in results}
    assert len(result_types) > 1  # At least 2 different types


def test_search_with_limit(populated_search):
    """Test search respects limit parameter."""
    results = populated_search.search("Python", limit=2)
    assert len(results) <= 2


def test_search_with_min_score(populated_search):
    """Test search respects minimum score."""
    results = populated_search.search("Python", min_score=50.0)
    assert all(r.score >= 50.0 for r in results)


def test_search_sorts_by_score(populated_search):
    """Test results are sorted by score (highest first)."""
    results = populated_search.search("Python")

    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


def test_calculate_score_exact_match(search_engine):
    """Test score calculation for exact matches."""
    score = search_engine._calculate_score("python", ["Learn Python programming"])
    assert score > 90  # Exact word match should score high


def test_calculate_score_partial_match(search_engine):
    """Test score calculation for partial matches."""
    score = search_engine._calculate_score("python programming", ["Learn Python basics"])
    assert 0 < score < 100  # Partial match


def test_calculate_score_no_match(search_engine):
    """Test score calculation when no match."""
    score = search_engine._calculate_score("python", ["JavaScript tutorial"])
    assert score == 0.0


def test_calculate_score_multiple_fields(search_engine):
    """Test score calculation across multiple fields."""
    score = search_engine._calculate_score(
        "python", ["JavaScript", "Python tutorial", "Programming"]
    )
    assert score > 0  # Should find match in second field


def test_truncate_long_text(search_engine):
    """Test text truncation."""
    long_text = "A" * 100
    truncated = search_engine._truncate(long_text, 50)
    assert len(truncated) == 50
    assert truncated.endswith("...")


def test_truncate_short_text(search_engine):
    """Test short text is not truncated."""
    short_text = "Short text"
    truncated = search_engine._truncate(short_text, 50)
    assert truncated == short_text


def test_get_stats(populated_search):
    """Test getting search statistics."""
    stats = populated_search.get_stats()

    assert "history" in stats
    assert "favorites" in stats
    assert "templates" in stats
    assert "snippets" in stats
    assert "collections" in stats

    assert stats["history"] > 0
    assert stats["favorites"] > 0
    assert stats["snippets"] > 0
    assert stats["collections"] > 0


def test_get_stats_empty(search_engine):
    """Test stats with empty data."""
    stats = search_engine.get_stats()

    assert all(isinstance(count, int) for count in stats.values())
    assert all(count >= 0 for count in stats.values())


def test_favorites_boost(populated_search):
    """Test that favorites get score boost."""
    # Add similar content to history and favorites
    populated_search.history_mgr.add(
        prompt_text="Test prompt for comparison",
        ir={"domain": "general", "language": "EN"},
        score=80.0,
    )

    populated_search.favorites_mgr.add(
        prompt_id="fav_test",
        prompt_text="Test prompt for comparison",
        tags=["test"],
        domain="general",
        score=80.0,
    )

    results = populated_search.search("Test prompt")

    favorite_results = [r for r in results if r.result_type == SearchResultType.FAVORITE]
    history_results = [r for r in results if r.result_type == SearchResultType.HISTORY]

    if favorite_results and history_results:
        # Favorites should be boosted (1.1x multiplier)
        assert favorite_results[0].score > history_results[0].score


def test_search_case_insensitive(populated_search):
    """Test search is case-insensitive."""
    results_lower = populated_search.search("python")
    results_upper = populated_search.search("PYTHON")
    results_mixed = populated_search.search("Python")

    # Should return same number of results regardless of case
    assert len(results_lower) == len(results_upper) == len(results_mixed)


def test_search_with_multiple_words(populated_search):
    """Test search with multiple words."""
    results = populated_search.search("machine learning python")

    # Should find results containing these terms
    assert len(results) > 0


def test_search_result_metadata(populated_search):
    """Test that results include metadata."""
    results = populated_search.search("Python")

    for result in results:
        assert "metadata" in result.to_dict()
        assert isinstance(result.metadata, dict)


def test_search_handles_special_characters(search_engine):
    """Test search handles special characters gracefully."""
    # Should not crash with special characters
    results = search_engine.search("C++ programming @#$%")
    assert isinstance(results, list)


def test_search_multiple_result_types_filter(populated_search):
    """Test filtering by multiple result types."""
    results = populated_search.search(
        "Python", result_types=[SearchResultType.HISTORY, SearchResultType.SNIPPET]
    )

    result_types = {r.result_type for r in results}
    assert result_types.issubset({SearchResultType.HISTORY, SearchResultType.SNIPPET})


def test_get_search_engine_singleton():
    """Test that get_search_engine returns singleton."""
    engine1 = get_search_engine()
    engine2 = get_search_engine()
    assert engine1 is engine2


def test_search_with_tags(populated_search):
    """Test searching finds content with matching tags."""
    results = populated_search.search("tutorial")

    # Should find snippet with 'tutorial' tag
    snippet_results = [r for r in results if r.result_type == SearchResultType.SNIPPET]
    assert len(snippet_results) > 0


def test_search_empty_database(search_engine):
    """Test search with empty database returns no results."""
    results = search_engine.search("anything")
    assert len(results) == 0


def test_search_score_range(populated_search):
    """Test that scores are within 0-100 range."""
    results = populated_search.search("Python")

    for result in results:
        assert 0 <= result.score <= 100


def test_search_by_domain(populated_search):
    """Test searching by domain keywords."""
    results = populated_search.search("education")

    # Should find history entry with education domain
    education_results = [r for r in results if r.metadata.get("domain") == "education"]
    assert len(education_results) > 0
