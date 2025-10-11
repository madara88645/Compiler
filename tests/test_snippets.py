"""Tests for snippets module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.snippets import Snippet, SnippetsManager


@pytest.fixture
def temp_snippets_file():
    """Create temporary snippets file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        snippets_path = Path(f.name)
    yield snippets_path
    if snippets_path.exists():
        snippets_path.unlink()


@pytest.fixture
def manager(temp_snippets_file):
    """Create SnippetsManager with temporary file."""
    return SnippetsManager(snippets_file=temp_snippets_file)


def test_snippets_manager_init(manager):
    """Test SnippetsManager initialization"""
    assert manager.snippets_file is not None
    assert manager._snippets == {}


def test_add_snippet(manager):
    """Test adding a new snippet"""
    snippet = manager.add(
        snippet_id="test1",
        title="Test Snippet",
        content="This is a test snippet content",
        category="constraint",
        description="A test snippet",
        tags=["test", "example"],
        language="en",
    )

    assert snippet.id == "test1"
    assert snippet.title == "Test Snippet"
    assert snippet.category == "constraint"
    assert len(snippet.tags) == 2
    assert snippet.use_count == 0


def test_add_duplicate_snippet(manager):
    """Test adding duplicate snippet raises error"""
    manager.add(
        snippet_id="duplicate",
        title="First",
        content="First content",
        category="constraint",
    )

    with pytest.raises(ValueError, match="already exists"):
        manager.add(
            snippet_id="duplicate",
            title="Second",
            content="Second content",
            category="constraint",
        )


def test_get_snippet(manager):
    """Test getting a snippet"""
    manager.add(
        snippet_id="get_test",
        title="Get Test",
        content="Test content",
        category="example",
    )

    snippet = manager.get("get_test")
    assert snippet is not None
    assert snippet.id == "get_test"

    # Non-existent snippet
    assert manager.get("nonexistent") is None


def test_get_all_snippets(manager):
    """Test getting all snippets"""
    manager.add(
        snippet_id="snippet1",
        title="Snippet 1",
        content="Content 1",
        category="constraint",
        tags=["python"],
    )

    manager.add(
        snippet_id="snippet2",
        title="Snippet 2",
        content="Content 2",
        category="example",
        tags=["javascript"],
    )

    # Get all
    all_snippets = manager.get_all()
    assert len(all_snippets) == 2

    # Filter by category
    constraints = manager.get_all(category="constraint")
    assert len(constraints) == 1
    assert constraints[0].id == "snippet1"

    # Filter by tags
    python_snippets = manager.get_all(tags=["python"])
    assert len(python_snippets) == 1
    assert python_snippets[0].id == "snippet1"


def test_search_snippets(manager):
    """Test searching snippets"""
    manager.add(
        snippet_id="search1",
        title="Python Tutorial",
        content="This is Python code",
        category="example",
    )

    manager.add(
        snippet_id="search2",
        title="JavaScript Guide",
        content="This is JavaScript code",
        category="example",
    )

    manager.add(
        snippet_id="search3",
        title="Python Data Science",
        content="Data science with Python",
        category="context",
        tags=["ml"],
    )

    # Search in title
    results = manager.search("Python")
    assert len(results) == 2

    # Search in content
    results = manager.search("JavaScript code")
    assert len(results) == 1
    assert results[0].id == "search2"

    # Search in tags
    results = manager.search("ml")
    assert len(results) == 1
    assert results[0].id == "search3"


def test_update_snippet(manager):
    """Test updating a snippet"""
    manager.add(
        snippet_id="update_test",
        title="Original Title",
        content="Original content",
        category="constraint",
        tags=["old"],
    )

    updated = manager.update(
        snippet_id="update_test",
        title="Updated Title",
        content="Updated content",
        tags=["new", "updated"],
    )

    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.content == "Updated content"
    assert "new" in updated.tags
    assert "updated" in updated.tags


def test_update_nonexistent_snippet(manager):
    """Test updating non-existent snippet returns None"""
    result = manager.update(
        snippet_id="nonexistent",
        title="New Title",
    )

    assert result is None


def test_delete_snippet(manager):
    """Test deleting a snippet"""
    manager.add(
        snippet_id="delete_test",
        title="Delete Test",
        content="Will be deleted",
        category="constraint",
    )

    # Verify exists
    assert manager.get("delete_test") is not None

    # Delete
    success = manager.delete("delete_test")
    assert success is True

    # Verify deleted
    assert manager.get("delete_test") is None


def test_delete_nonexistent_snippet(manager):
    """Test deleting non-existent snippet returns False"""
    success = manager.delete("nonexistent")
    assert success is False


def test_use_snippet(manager):
    """Test using a snippet"""
    manager.add(
        snippet_id="use_test",
        title="Use Test",
        content="This is the content to use",
        category="example",
    )

    content = manager.use("use_test")
    assert content == "This is the content to use"

    # Check use count incremented
    snippet = manager.get("use_test")
    assert snippet.use_count == 1
    assert snippet.last_used is not None

    # Use again
    manager.use("use_test")
    snippet = manager.get("use_test")
    assert snippet.use_count == 2


def test_use_nonexistent_snippet(manager):
    """Test using non-existent snippet returns None"""
    content = manager.use("nonexistent")
    assert content is None


def test_add_tag(manager):
    """Test adding a tag to snippet"""
    manager.add(
        snippet_id="tag_test",
        title="Tag Test",
        content="Content",
        category="constraint",
        tags=["initial"],
    )

    success = manager.add_tag("tag_test", "new_tag")
    assert success is True

    snippet = manager.get("tag_test")
    assert "new_tag" in snippet.tags
    assert "initial" in snippet.tags


def test_remove_tag(manager):
    """Test removing a tag from snippet"""
    manager.add(
        snippet_id="untag_test",
        title="Untag Test",
        content="Content",
        category="constraint",
        tags=["tag1", "tag2", "tag3"],
    )

    success = manager.remove_tag("untag_test", "tag2")
    assert success is True

    snippet = manager.get("untag_test")
    assert "tag2" not in snippet.tags
    assert "tag1" in snippet.tags
    assert "tag3" in snippet.tags


def test_get_categories(manager):
    """Test getting all categories"""
    manager.add(
        snippet_id="cat1",
        title="Cat 1",
        content="Content 1",
        category="constraint",
    )

    manager.add(
        snippet_id="cat2",
        title="Cat 2",
        content="Content 2",
        category="example",
    )

    manager.add(
        snippet_id="cat3",
        title="Cat 3",
        content="Content 3",
        category="context",
    )

    categories = manager.get_categories()
    assert len(categories) == 3
    assert "constraint" in categories
    assert "example" in categories
    assert "context" in categories


def test_get_most_used(manager):
    """Test getting most used snippets"""
    manager.add("snippet1", "Snippet 1", "Content 1", "constraint")
    manager.add("snippet2", "Snippet 2", "Content 2", "example")
    manager.add("snippet3", "Snippet 3", "Content 3", "context")

    # Use snippets
    manager.use("snippet1")
    manager.use("snippet1")
    manager.use("snippet1")
    manager.use("snippet2")
    manager.use("snippet2")
    manager.use("snippet3")

    most_used = manager.get_most_used(limit=2)
    assert len(most_used) == 2
    assert most_used[0].id == "snippet1"
    assert most_used[0].use_count == 3
    assert most_used[1].id == "snippet2"
    assert most_used[1].use_count == 2


def test_get_stats(manager):
    """Test getting statistics"""
    manager.add(
        snippet_id="stats1",
        title="Stats 1",
        content="Content 1",
        category="constraint",
        language="en",
    )

    manager.add(
        snippet_id="stats2",
        title="Stats 2",
        content="Content 2",
        category="example",
        language="en",
    )

    manager.add(
        snippet_id="stats3",
        title="Stats 3",
        content="Content 3",
        category="constraint",
        language="tr",
    )

    # Use some snippets
    manager.use("stats1")
    manager.use("stats1")
    manager.use("stats2")

    stats = manager.get_stats()

    assert stats["total_snippets"] == 3
    assert stats["total_uses"] == 3
    assert stats["categories"]["constraint"] == 2
    assert stats["categories"]["example"] == 1
    assert stats["languages"]["en"] == 2
    assert stats["languages"]["tr"] == 1
    assert len(stats["most_used"]) > 0


def test_get_stats_empty(manager):
    """Test getting statistics with no snippets"""
    stats = manager.get_stats()

    assert stats["total_snippets"] == 0
    assert stats["total_uses"] == 0
    assert stats["categories"] == {}
    assert stats["languages"] == {}
    assert stats["most_used"] == []


def test_clear_snippets(manager):
    """Test clearing all snippets"""
    manager.add("snippet1", "Snippet 1", "Content 1", "constraint")
    manager.add("snippet2", "Snippet 2", "Content 2", "example")

    assert len(manager.get_all()) == 2

    manager.clear()

    assert len(manager.get_all()) == 0


def test_snippet_to_dict_and_from_dict():
    """Test snippet serialization"""
    original = Snippet(
        id="test",
        title="Test Snippet",
        content="Test content",
        category="constraint",
        description="Test description",
        tags=["tag1", "tag2"],
        use_count=5,
        language="en",
    )

    # Convert to dict
    data = original.to_dict()
    assert data["id"] == "test"
    assert data["title"] == "Test Snippet"
    assert len(data["tags"]) == 2

    # Convert back to Snippet
    restored = Snippet.from_dict(data)
    assert restored.id == original.id
    assert restored.title == original.title
    assert restored.content == original.content
    assert restored.tags == original.tags
    assert restored.use_count == original.use_count


def test_persistence(temp_snippets_file):
    """Test that snippets persist across manager instances"""
    manager1 = SnippetsManager(snippets_file=temp_snippets_file)

    manager1.add(
        snippet_id="persist_test",
        title="Persist Test",
        content="Persistent content",
        category="constraint",
    )

    manager1.use("persist_test")

    # Create new manager with same file
    manager2 = SnippetsManager(snippets_file=temp_snippets_file)

    snippet = manager2.get("persist_test")
    assert snippet is not None
    assert snippet.title == "Persist Test"
    assert snippet.use_count == 1


def test_language_filtering(manager):
    """Test filtering by language"""
    manager.add("en1", "English 1", "Content", "constraint", language="en")
    manager.add("en2", "English 2", "Content", "example", language="en")
    manager.add("tr1", "Turkish 1", "İçerik", "constraint", language="tr")

    en_snippets = manager.get_all(language="en")
    assert len(en_snippets) == 2

    tr_snippets = manager.get_all(language="tr")
    assert len(tr_snippets) == 1


def test_multiple_tag_filtering(manager):
    """Test filtering by multiple tags"""
    manager.add("multi1", "Multi 1", "Content", "constraint", tags=["python", "advanced"])
    manager.add("multi2", "Multi 2", "Content", "example", tags=["python"])
    manager.add("multi3", "Multi 3", "Content", "context", tags=["python", "advanced", "ml"])

    # Both tags required
    results = manager.get_all(tags=["python", "advanced"])
    assert len(results) == 2
    assert all("python" in s.tags and "advanced" in s.tags for s in results)
