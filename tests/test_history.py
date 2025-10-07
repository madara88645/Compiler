"""
Tests for history module
"""

import pytest
from pathlib import Path
import tempfile
from app.history import HistoryManager, HistoryEntry


@pytest.fixture
def temp_history():
    """Create a temporary history file for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "history.json"
        yield history_file


def test_history_manager_init(temp_history):
    """Test history manager initialization"""
    manager = HistoryManager(history_file=temp_history)
    # File created on first save, not on init
    assert len(manager.entries) == 0
    assert manager.history_file == temp_history


def test_add_entry(temp_history):
    """Test adding entries to history"""
    manager = HistoryManager(history_file=temp_history)
    
    ir = {
        "domain": "education",
        "language": "en",
        "intents": ["teach"],
    }
    
    manager.add("Test prompt for history", ir, score=85.5)
    
    assert len(manager.entries) == 1
    assert manager.entries[0].domain == "education"
    assert manager.entries[0].language == "en"
    assert manager.entries[0].score == 85.5


def test_get_recent(temp_history):
    """Test retrieving recent entries"""
    manager = HistoryManager(history_file=temp_history, max_entries=50)
    
    # Add multiple entries
    for i in range(10):
        ir = {
            "domain": "general",
            "language": "en",
        }
        manager.add(f"Prompt {i}", ir, score=70.0 + i)
    
    recent = manager.get_recent(limit=5)
    assert len(recent) == 5
    
    # Should be in reverse order (newest first)
    assert "Prompt 9" in recent[0].prompt_text
    assert "Prompt 8" in recent[1].prompt_text


def test_search(temp_history):
    """Test searching history"""
    manager = HistoryManager(history_file=temp_history)
    
    manager.add("Python programming tutorial", {"domain": "education", "language": "en"})
    manager.add("JavaScript basics guide", {"domain": "education", "language": "en"})
    manager.add("Python data science", {"domain": "tech", "language": "en"})
    
    results = manager.search("Python")
    assert len(results) == 2
    
    results = manager.search("JavaScript")
    assert len(results) == 1


def test_get_by_domain(temp_history):
    """Test filtering by domain"""
    manager = HistoryManager(history_file=temp_history)
    
    manager.add("Education prompt 1", {"domain": "education", "language": "en"})
    manager.add("Education prompt 2", {"domain": "education", "language": "en"})
    manager.add("Tech prompt", {"domain": "tech", "language": "en"})
    
    education_entries = manager.get_by_domain("education")
    assert len(education_entries) == 2
    
    tech_entries = manager.get_by_domain("tech")
    assert len(tech_entries) == 1


def test_get_by_id(temp_history):
    """Test retrieving entry by ID"""
    manager = HistoryManager(history_file=temp_history)
    
    manager.add("Test prompt", {"domain": "general", "language": "en"})
    
    entry_id = manager.entries[0].id
    entry = manager.get_by_id(entry_id)
    
    assert entry is not None
    assert entry.prompt_text == "Test prompt"


def test_clear(temp_history):
    """Test clearing history"""
    manager = HistoryManager(history_file=temp_history)
    
    for i in range(5):
        manager.add(f"Prompt {i}", {"domain": "general", "language": "en"})
    
    assert len(manager.entries) == 5
    
    manager.clear()
    assert len(manager.entries) == 0


def test_get_stats(temp_history):
    """Test history statistics"""
    manager = HistoryManager(history_file=temp_history)
    
    # Add entries with different domains and languages
    manager.add("English education", {"domain": "education", "language": "en"}, score=85.0)
    manager.add("English tech", {"domain": "tech", "language": "en"}, score=90.0)
    manager.add("Turkish education", {"domain": "education", "language": "tr"}, score=75.0)
    
    stats = manager.get_stats()
    
    assert stats["total"] == 3
    assert stats["avg_score"] == 83.33  # (85 + 90 + 75) / 3
    assert stats["domains"]["education"] == 2
    assert stats["domains"]["tech"] == 1
    assert stats["languages"]["en"] == 2
    assert stats["languages"]["tr"] == 1


def test_max_entries_limit(temp_history):
    """Test that history respects max entries limit"""
    manager = HistoryManager(history_file=temp_history, max_entries=10)
    
    # Add more than max_entries
    for i in range(15):
        manager.add(f"Prompt {i}", {"domain": "general", "language": "en"})
    
    # Should be capped at max_entries
    assert len(manager.entries) == 10
    
    # Should keep newest entries
    assert "Prompt 14" in manager.entries[-1].prompt_text


def test_persistence(temp_history):
    """Test that history persists across instances"""
    manager1 = HistoryManager(history_file=temp_history)
    manager1.add("Test prompt", {"domain": "general", "language": "en"}, score=80.0)
    
    # Create new instance with same file
    manager2 = HistoryManager(history_file=temp_history)
    
    assert len(manager2.entries) == 1
    assert manager2.entries[0].prompt_text == "Test prompt"
    assert manager2.entries[0].score == 80.0


def test_empty_stats(temp_history):
    """Test stats with empty history"""
    manager = HistoryManager(history_file=temp_history)
    
    stats = manager.get_stats()
    
    assert stats["total"] == 0
    assert stats["avg_score"] == 0.0
    assert stats["domains"] == {}
    assert stats["languages"] == {}


def test_entry_to_dict_and_from_dict():
    """Test HistoryEntry serialization"""
    entry = HistoryEntry(
        id="test123",
        prompt_text="Test prompt",
        prompt_hash="hash123",
        domain="education",
        language="en",
        score=85.5,
        ir_version="v2",
        tags=["test", "demo"],
    )
    
    # Convert to dict
    data = entry.to_dict()
    assert data["id"] == "test123"
    assert data["domain"] == "education"
    assert data["score"] == 85.5
    
    # Convert back from dict
    entry2 = HistoryEntry.from_dict(data)
    assert entry2.id == entry.id
    assert entry2.domain == entry.domain
    assert entry2.score == entry.score


def test_truncate_long_prompt(temp_history):
    """Test that long prompts are truncated"""
    manager = HistoryManager(history_file=temp_history)
    
    long_prompt = "A" * 1000  # 1000 characters
    manager.add(long_prompt, {"domain": "general", "language": "en"})
    
    entry = manager.entries[0]
    assert len(entry.prompt_text) == 500  # Truncated to 500
