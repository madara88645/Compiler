"""Tests for search history manager."""

import json
import pytest
from pathlib import Path
from datetime import datetime
from app.search_history import (
    SearchHistoryEntry,
    SearchHistoryManager,
    get_search_history_manager,
)


@pytest.fixture
def temp_history_path(tmp_path):
    """Create temporary history file path."""
    return tmp_path / "test_search_history.json"


@pytest.fixture
def history_manager(temp_history_path):
    """Create SearchHistoryManager with temporary path."""
    return SearchHistoryManager(storage_path=temp_history_path)


def test_search_history_entry_creation():
    """Test creating a search history entry."""
    entry = SearchHistoryEntry(
        query="test query",
        result_count=5,
        types_filter=["prompt", "template"],
        min_score=0.5,
    )
    assert entry.query == "test query"
    assert entry.result_count == 5
    assert entry.types_filter == ["prompt", "template"]
    assert entry.min_score == 0.5
    assert entry.timestamp is not None


def test_search_history_entry_to_dict():
    """Test converting entry to dictionary."""
    entry = SearchHistoryEntry(query="test", result_count=3)
    data = entry.to_dict()
    assert isinstance(data, dict)
    assert data["query"] == "test"
    assert data["result_count"] == 3
    assert "timestamp" in data


def test_search_history_entry_from_dict():
    """Test creating entry from dictionary."""
    data = {
        "query": "test query",
        "result_count": 10,
        "timestamp": datetime.now().isoformat(),
        "types_filter": ["snippet"],
        "min_score": 0.7,
    }
    entry = SearchHistoryEntry.from_dict(data)
    assert entry.query == "test query"
    assert entry.result_count == 10
    assert entry.types_filter == ["snippet"]
    assert entry.min_score == 0.7


def test_history_manager_initialization(history_manager, temp_history_path):
    """Test history manager initialization."""
    assert history_manager.storage_path == temp_history_path
    assert isinstance(history_manager._entries, list)
    assert len(history_manager._entries) == 0


def test_add_entry(history_manager):
    """Test adding a search entry."""
    history_manager.add("test search", 5)
    entries = history_manager.get_recent()
    assert len(entries) == 1
    assert entries[0].query == "test search"
    assert entries[0].result_count == 5


def test_add_entry_with_filters(history_manager):
    """Test adding entry with type filters."""
    history_manager.add("filtered search", 3, types_filter=["template", "snippet"], min_score=0.8)
    entries = history_manager.get_recent()
    assert len(entries) == 1
    assert entries[0].types_filter == ["template", "snippet"]
    assert entries[0].min_score == 0.8


def test_add_multiple_entries(history_manager):
    """Test adding multiple entries."""
    for i in range(5):
        history_manager.add(f"query {i}", i)
    entries = history_manager.get_recent()
    assert len(entries) == 5


def test_max_entries_limit(history_manager):
    """Test that history keeps only last 10 entries."""
    for i in range(15):
        history_manager.add(f"query {i}", i)
    entries = history_manager.get_recent()
    assert len(entries) == 10
    # Should keep the most recent ones (5-14)
    assert entries[0].query == "query 14"
    assert entries[-1].query == "query 5"


def test_get_recent_with_limit(history_manager):
    """Test getting recent entries with limit."""
    for i in range(8):
        history_manager.add(f"query {i}", i)
    entries = history_manager.get_recent(limit=3)
    assert len(entries) == 3
    assert entries[0].query == "query 7"


def test_get_by_index(history_manager):
    """Test getting entry by index."""
    history_manager.add("query 1", 1)
    history_manager.add("query 2", 2)
    history_manager.add("query 3", 3)

    # Most recent is index 0
    entry = history_manager.get_by_index(0)
    assert entry.query == "query 3"

    entry = history_manager.get_by_index(2)
    assert entry.query == "query 1"


def test_get_by_index_out_of_range(history_manager):
    """Test getting entry with invalid index."""
    history_manager.add("query", 1)
    entry = history_manager.get_by_index(5)
    assert entry is None


def test_clear_history(history_manager):
    """Test clearing all history."""
    history_manager.add("query 1", 1)
    history_manager.add("query 2", 2)
    assert len(history_manager.get_recent()) == 2

    history_manager.clear()
    assert len(history_manager.get_recent()) == 0


def test_persistence(temp_history_path):
    """Test that history is persisted to disk."""
    # Create manager and add entries
    manager1 = SearchHistoryManager(storage_path=temp_history_path)
    manager1.add("persistent query", 5)

    # Create new manager with same path
    manager2 = SearchHistoryManager(storage_path=temp_history_path)
    entries = manager2.get_recent()

    assert len(entries) == 1
    assert entries[0].query == "persistent query"
    assert entries[0].result_count == 5


def test_persistence_after_clear(temp_history_path):
    """Test that cleared history is persisted."""
    manager1 = SearchHistoryManager(storage_path=temp_history_path)
    manager1.add("query", 1)
    manager1.clear()

    manager2 = SearchHistoryManager(storage_path=temp_history_path)
    assert len(manager2.get_recent()) == 0


def test_corrupted_file_handling(temp_history_path):
    """Test handling of corrupted history file."""
    # Write invalid JSON
    with open(temp_history_path, "w") as f:
        f.write("invalid json{{{")

    manager = SearchHistoryManager(storage_path=temp_history_path)
    assert len(manager.get_recent()) == 0


def test_get_search_history_manager():
    """Test singleton manager getter."""
    manager1 = get_search_history_manager()
    manager2 = get_search_history_manager()
    assert manager1 is manager2


def test_empty_history_get_recent(history_manager):
    """Test getting recent from empty history."""
    entries = history_manager.get_recent()
    assert entries == []


def test_empty_history_get_by_index(history_manager):
    """Test getting by index from empty history."""
    entry = history_manager.get_by_index(0)
    assert entry is None


def test_json_serialization(history_manager, temp_history_path):
    """Test that entries are properly serialized to JSON."""
    history_manager.add("test query", 3, types_filter=["template"], min_score=0.5)

    with open(temp_history_path, "r") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["query"] == "test query"
    assert data[0]["result_count"] == 3
    assert data[0]["types_filter"] == ["template"]
    assert data[0]["min_score"] == 0.5
    assert "timestamp" in data[0]


def test_timestamp_format(history_manager):
    """Test that timestamp is in ISO format."""
    history_manager.add("query", 1)
    entries = history_manager.get_recent()
    timestamp = entries[0].timestamp

    # Should be parseable as ISO format
    parsed = datetime.fromisoformat(timestamp)
    assert isinstance(parsed, datetime)


def test_none_types_filter(history_manager):
    """Test adding entry with None types_filter."""
    history_manager.add("query", 5, types_filter=None)
    entries = history_manager.get_recent()
    assert entries[0].types_filter is None


def test_storage_path_creation(tmp_path):
    """Test that storage directory is created if it doesn't exist."""
    nested_path = tmp_path / "nested" / "dirs" / "history.json"
    SearchHistoryManager(storage_path=nested_path)
    assert nested_path.parent.exists()


def test_default_storage_path():
    """Test that default storage path is used when None provided."""
    manager = SearchHistoryManager(storage_path=None)
    expected_path = Path.home() / ".promptc" / "search_history.json"
    assert manager.storage_path == expected_path
