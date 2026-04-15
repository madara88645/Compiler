import pytest
from datetime import datetime
from pydantic import ValidationError
from app.history.models import HistoryEntry


def test_history_entry_defaults():
    """Test creation with only required fields to verify default values."""
    entry = HistoryEntry(id="test-id-1", prompt_text="Hello world")

    assert entry.id == "test-id-1"
    assert entry.prompt_text == "Hello world"
    assert isinstance(entry.timestamp, datetime)
    assert entry.source == "user"
    assert entry.parent_id is None


def test_history_entry_full_initialization():
    """Test creation with all fields provided."""
    custom_time = datetime(2023, 1, 1, 12, 0, 0)
    entry = HistoryEntry(
        id="test-id-2",
        timestamp=custom_time,
        prompt_text="Custom prompt",
        source="system",
        parent_id="parent-123",
    )

    assert entry.id == "test-id-2"
    assert entry.timestamp == custom_time
    assert entry.prompt_text == "Custom prompt"
    assert entry.source == "system"
    assert entry.parent_id == "parent-123"


def test_history_entry_missing_required_fields():
    """Test validation errors for missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        HistoryEntry(prompt_text="Missing ID")
    assert "id\n  Field required" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        HistoryEntry(id="test-id-3")
    assert "prompt_text\n  Field required" in str(exc_info.value)


def test_history_entry_type_validation():
    """Test type validation and coercion behavior."""
    # Invalid timestamp string
    with pytest.raises(ValidationError) as exc_info:
        HistoryEntry(
            id="test-id-5",
            prompt_text="Type test",
            timestamp="invalid-date",  # type: ignore
        )
    assert "timestamp" in str(exc_info.value)
