from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from app.history.manager import HistoryManager
from app.history.models import HistoryEntry


@pytest.fixture
def temp_db_path(tmp_path):
    # Provide a temporary file path for the database
    db_file = tmp_path / "test_history.db"
    return str(db_file)


@pytest.fixture
def manager(temp_db_path):
    return HistoryManager(db_path=temp_db_path)


def test_init_db(temp_db_path):
    HistoryManager(db_path=temp_db_path)

    # Check if directory was created
    assert Path(temp_db_path).parent.exists()

    # Check if table exists
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
    assert cur.fetchone() is not None
    conn.close()


def test_save_and_get_by_id(manager):
    entry = HistoryEntry(
        id="test-id-1",
        prompt_text="Test prompt",
        source="test",
        metadata={"key": "value"},
        score=0.95,
    )

    # Save entry
    manager.save(entry)

    # Retrieve entry
    retrieved = manager.get_by_id("test-id-1")
    assert retrieved is not None
    assert retrieved.id == "test-id-1"
    assert retrieved.prompt_text == "Test prompt"
    assert retrieved.source == "test"
    assert retrieved.metadata == {"key": "value"}
    assert retrieved.score == 0.95

    # Ensure getting a non-existent id returns None
    assert manager.get_by_id("non-existent") is None


def test_save_updates_existing(manager):
    entry1 = HistoryEntry(id="test-id-2", prompt_text="Initial text")
    manager.save(entry1)

    entry2 = HistoryEntry(id="test-id-2", prompt_text="Updated text")
    manager.save(entry2)

    retrieved = manager.get_by_id("test-id-2")
    assert retrieved.prompt_text == "Updated text"


def test_list_recent(manager):
    # Insert multiple entries
    entries = []
    for i in range(5):
        entry = HistoryEntry(id=f"id-{i}", prompt_text=f"Prompt {i}")
        manager.save(entry)
        entries.append(entry)

    recent = manager.list_recent(limit=3)
    assert len(recent) == 3

    # Verify we got HistoryEntry objects back
    assert all(isinstance(e, HistoryEntry) for e in recent)

    all_recent = manager.list_recent(limit=10)
    assert len(all_recent) == 5


def test_list_recent_filters_by_source_before_limit(manager):
    base = datetime(2026, 1, 1, 12, 0, 0)
    entries = [
        HistoryEntry(
            id="evolution-old",
            prompt_text="Older optimizer entry",
            source="evolution",
            timestamp=base,
        ),
        HistoryEntry(
            id="evolution-new",
            prompt_text="Newer optimizer entry",
            source="evolution",
            timestamp=base + timedelta(minutes=1),
        ),
        HistoryEntry(
            id="user-newer",
            prompt_text="Newer user entry",
            source="user",
            timestamp=base + timedelta(minutes=2),
        ),
        HistoryEntry(
            id="user-newest",
            prompt_text="Newest user entry",
            source="user",
            timestamp=base + timedelta(minutes=3),
        ),
    ]
    for entry in entries:
        manager.save(entry)

    recent = manager.list_recent(limit=2, source="evolution")

    assert [entry.id for entry in recent] == ["evolution-new", "evolution-old"]


def test_search_and_stats_use_the_real_sqlite_store(manager):
    manager.save(
        HistoryEntry(
            id="optimizer-entry",
            prompt_text="Explain retry budgets clearly",
            source="evolution",
            score=87.5,
            metadata={"run_id": "run-1"},
        )
    )
    manager.save(
        HistoryEntry(
            id="user-entry",
            prompt_text="Draft a release note",
            source="user",
        )
    )

    matches = manager.search("retry", limit=10)
    stats = manager.get_stats()

    assert [entry.id for entry in matches] == ["optimizer-entry"]
    assert stats["total"] == 2
    assert stats["first"] is not None
    assert stats["last"] is not None


def test_history_entry_to_dict_is_cli_serializable():
    entry = HistoryEntry(id="json-entry", prompt_text="JSON ready")

    payload = entry.to_dict()

    assert payload["id"] == "json-entry"
    assert isinstance(payload["timestamp"], str)


def test_get_history_manager_singleton(monkeypatch, temp_db_path):
    # Mock default arg in __init__ instead of module constant because the
    # module constant is likely already evaluated at import time by Python.
    # A cleaner approach is to set global manager to None and patch the default.

    import app.history.manager as hm

    # Store original
    orig_init = hm.HistoryManager.__init__

    def mock_init(self, db_path=temp_db_path):
        orig_init(self, db_path=temp_db_path)

    monkeypatch.setattr(hm.HistoryManager, "__init__", mock_init)

    # Reset global manager state for test isolation
    monkeypatch.setattr(hm, "_global_manager", None)

    manager1 = hm.get_history_manager()
    manager2 = hm.get_history_manager()

    assert manager1 is manager2
    assert manager1.db_path == temp_db_path
