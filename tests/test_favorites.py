"""Tests for favorites/bookmarks functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.favorites import FavoritesManager


@pytest.fixture
def temp_favorites_file():
    """Create temporary favorites file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink()


def test_favorites_manager_init(temp_favorites_file):
    """Test favorites manager initialization"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)
    assert manager.favorites_file == temp_favorites_file
    assert len(manager.entries) == 0


def test_add_favorite(temp_favorites_file):
    """Test adding a favorite"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(
        prompt_id="test123",
        prompt_text="Test favorite prompt",
        domain="education",
        language="en",
        score=85.5,
        tags=["python", "tutorial"],
        notes="Great example",
    )

    assert entry.prompt_id == "test123"
    assert entry.domain == "education"
    assert entry.language == "en"
    assert entry.score == 85.5
    assert "python" in entry.tags
    assert "tutorial" in entry.tags
    assert entry.notes == "Great example"
    assert len(manager.entries) == 1


def test_add_duplicate_favorite(temp_favorites_file):
    """Test adding same favorite twice updates existing"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    # Add first time
    manager.add(
        prompt_id="test123",
        prompt_text="Test prompt",
        domain="general",
        tags=["tag1"],
    )

    assert len(manager.entries) == 1

    # Add again with new tags
    manager.add(
        prompt_id="test123",
        prompt_text="Test prompt",
        domain="general",
        tags=["tag2"],
        notes="Updated notes",
    )

    # Should still be 1 entry, but updated
    assert len(manager.entries) == 1
    assert "tag1" in manager.entries[0].tags
    assert "tag2" in manager.entries[0].tags
    assert manager.entries[0].notes == "Updated notes"


def test_remove_favorite(temp_favorites_file):
    """Test removing a favorite"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(
        prompt_id="test123",
        prompt_text="Test prompt",
        domain="general",
    )

    assert len(manager.entries) == 1

    # Remove by ID
    removed = manager.remove(entry.id)
    assert removed is True
    assert len(manager.entries) == 0

    # Try removing non-existent
    removed = manager.remove("nonexistent")
    assert removed is False


def test_get_all_favorites(temp_favorites_file):
    """Test getting all favorites"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    manager.add(prompt_id="test1", prompt_text="Prompt 1", domain="education")
    manager.add(prompt_id="test2", prompt_text="Prompt 2", domain="tech")
    manager.add(prompt_id="test3", prompt_text="Prompt 3", domain="education", tags=["python"])

    # Get all
    all_favorites = manager.get_all()
    assert len(all_favorites) == 3

    # Filter by domain
    edu_favorites = manager.get_all(domain="education")
    assert len(edu_favorites) == 2

    # Filter by tags
    python_favorites = manager.get_all(tags=["python"])
    assert len(python_favorites) == 1


def test_get_by_id(temp_favorites_file):
    """Test getting favorite by ID"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(
        prompt_id="test123",
        prompt_text="Test prompt",
        domain="general",
    )

    # Get by ID
    found = manager.get_by_id(entry.id)
    assert found is not None
    assert found.prompt_id == "test123"

    # Try non-existent
    not_found = manager.get_by_id("nonexistent")
    assert not_found is None


def test_search_favorites(temp_favorites_file):
    """Test searching favorites"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    manager.add(prompt_id="test1", prompt_text="Python programming tutorial", domain="education")
    manager.add(prompt_id="test2", prompt_text="JavaScript guide", domain="tech")
    manager.add(
        prompt_id="test3", prompt_text="Python data science", domain="tech", notes="ML focus"
    )

    # Search in prompt text
    results = manager.search("Python")
    assert len(results) == 2

    # Search in notes
    results = manager.search("ML")
    assert len(results) == 1

    # Search in tags
    manager.add(prompt_id="test4", prompt_text="Tutorial", tags=["python"])
    results = manager.search("python")
    assert len(results) == 3


def test_add_tag(temp_favorites_file):
    """Test adding tags to favorite"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(prompt_id="test123", prompt_text="Test prompt", tags=["tag1"])

    # Add new tag
    success = manager.add_tag(entry.id, "tag2")
    assert success is True

    updated = manager.get_by_id(entry.id)
    assert "tag1" in updated.tags
    assert "tag2" in updated.tags

    # Try adding to non-existent
    success = manager.add_tag("nonexistent", "tag3")
    assert success is False


def test_remove_tag(temp_favorites_file):
    """Test removing tags from favorite"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(prompt_id="test123", prompt_text="Test prompt", tags=["tag1", "tag2"])

    # Remove tag
    success = manager.remove_tag(entry.id, "tag1")
    assert success is True

    updated = manager.get_by_id(entry.id)
    assert "tag1" not in updated.tags
    assert "tag2" in updated.tags


def test_update_notes(temp_favorites_file):
    """Test updating notes"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(prompt_id="test123", prompt_text="Test prompt", notes="Original notes")

    # Update notes
    success = manager.update_notes(entry.id, "Updated notes")
    assert success is True

    updated = manager.get_by_id(entry.id)
    assert updated.notes == "Updated notes"


def test_increment_use_count(temp_favorites_file):
    """Test incrementing use count"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry = manager.add(prompt_id="test123", prompt_text="Test prompt")
    assert entry.use_count == 0

    # Increment
    manager.increment_use_count(entry.id)
    updated = manager.get_by_id(entry.id)
    assert updated.use_count == 1

    # Increment again
    manager.increment_use_count(entry.id)
    updated = manager.get_by_id(entry.id)
    assert updated.use_count == 2


def test_get_most_used(temp_favorites_file):
    """Test getting most used favorites"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    entry1 = manager.add(prompt_id="test1", prompt_text="Prompt 1")
    entry2 = manager.add(prompt_id="test2", prompt_text="Prompt 2")
    entry3 = manager.add(prompt_id="test3", prompt_text="Prompt 3")

    # Set different use counts
    for _ in range(5):
        manager.increment_use_count(entry1.id)
    for _ in range(10):
        manager.increment_use_count(entry2.id)
    for _ in range(3):
        manager.increment_use_count(entry3.id)

    # Get most used
    most_used = manager.get_most_used(limit=2)
    assert len(most_used) == 2
    assert most_used[0].prompt_id == "test2"  # 10 uses
    assert most_used[1].prompt_id == "test1"  # 5 uses


def test_get_stats(temp_favorites_file):
    """Test getting statistics"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    manager.add(
        prompt_id="test1",
        prompt_text="Prompt 1",
        domain="education",
        language="en",
        score=85.0,
        tags=["python"],
    )
    manager.add(
        prompt_id="test2",
        prompt_text="Prompt 2",
        domain="tech",
        language="en",
        score=90.0,
        tags=["python", "tutorial"],
    )
    manager.add(
        prompt_id="test3", prompt_text="Prompt 3", domain="education", language="tr", score=75.0
    )

    stats = manager.get_stats()

    assert stats["total"] == 3
    assert stats["avg_score"] == 83.33
    assert stats["domains"]["education"] == 2
    assert stats["domains"]["tech"] == 1
    assert stats["tags"]["python"] == 2
    assert stats["tags"]["tutorial"] == 1
    assert stats["languages"]["en"] == 2
    assert stats["languages"]["tr"] == 1


def test_get_stats_empty(temp_favorites_file):
    """Test stats with no favorites"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    stats = manager.get_stats()

    assert stats["total"] == 0
    assert stats["avg_score"] == 0.0
    assert stats["domains"] == {}
    assert stats["tags"] == {}


def test_clear_favorites(temp_favorites_file):
    """Test clearing all favorites"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    manager.add(prompt_id="test1", prompt_text="Prompt 1")
    manager.add(prompt_id="test2", prompt_text="Prompt 2")

    assert len(manager.entries) == 2

    manager.clear()
    assert len(manager.entries) == 0


def test_persistence(temp_favorites_file):
    """Test that favorites persist across instances"""
    manager1 = FavoritesManager(favorites_file=temp_favorites_file)
    manager1.add(prompt_id="test123", prompt_text="Test prompt", domain="general", score=80.0)

    # Create new instance with same file
    manager2 = FavoritesManager(favorites_file=temp_favorites_file)

    assert len(manager2.entries) == 1
    assert manager2.entries[0].prompt_id == "test123"
    assert manager2.entries[0].score == 80.0


def test_truncate_long_prompt(temp_favorites_file):
    """Test that long prompts are truncated"""
    manager = FavoritesManager(favorites_file=temp_favorites_file)

    long_prompt = "A" * 1000
    entry = manager.add(prompt_id="test123", prompt_text=long_prompt)

    assert len(entry.prompt_text) == 500


def test_entry_to_dict_and_from_dict():
    """Test entry serialization"""
    from app.favorites import FavoriteEntry

    entry = FavoriteEntry(
        id="fav123",
        prompt_id="test123",
        timestamp="2025-10-08T10:00:00",
        prompt_text="Test prompt",
        domain="education",
        language="en",
        score=85.5,
        tags=["python", "tutorial"],
        notes="Great example",
        use_count=5,
    )

    # Convert to dict
    data = entry.to_dict()
    assert data["id"] == "fav123"
    assert data["prompt_id"] == "test123"
    assert data["score"] == 85.5
    assert data["use_count"] == 5

    # Convert back from dict
    entry2 = FavoriteEntry.from_dict(data)
    assert entry2.id == entry.id
    assert entry2.prompt_id == entry.prompt_id
    assert entry2.score == entry.score
    assert entry2.use_count == entry.use_count
