"""Tests for export/import functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.export_import import ExportImportManager


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_analytics_data():
    """Sample analytics records"""
    return [
        {
            "timestamp": "2025-10-07T10:00:00",
            "prompt_text": "Teach me Python",
            "prompt_hash": "abc123",
            "validation_score": 85.5,
            "domain": "education",
            "persona": "teacher",
            "language": "en",
            "intents": ["teach"],
            "issues_count": 2,
            "warnings_count": 1,
            "prompt_length": 15,
            "ir_version": "v2",
            "tags": ["programming"],
        },
        {
            "timestamp": "2025-10-07T11:00:00",
            "prompt_text": "Compare Python vs JavaScript",
            "prompt_hash": "def456",
            "validation_score": 78.0,
            "domain": "tech",
            "persona": "expert",
            "language": "en",
            "intents": ["compare"],
            "issues_count": 1,
            "warnings_count": 0,
            "prompt_length": 28,
            "ir_version": "v2",
            "tags": ["comparison"],
        },
    ]


@pytest.fixture
def sample_history_data():
    """Sample history entries"""
    return [
        {
            "id": "hist1",
            "timestamp": "2025-10-07T10:00:00",
            "prompt_text": "Teach me Python",
            "prompt_hash": "abc123",
            "domain": "education",
            "language": "en",
            "score": 85.5,
            "ir_version": "v2",
            "tags": ["programming"],
        },
        {
            "id": "hist2",
            "timestamp": "2025-10-07T11:00:00",
            "prompt_text": "Compare Python vs JavaScript",
            "prompt_hash": "def456",
            "domain": "tech",
            "language": "en",
            "score": 78.0,
            "ir_version": "v2",
            "tags": ["comparison"],
        },
    ]


def test_export_import_manager_init(temp_dir):
    """Test manager initialization"""
    analytics_db = temp_dir / "analytics.db"
    history_file = temp_dir / "history.json"

    manager = ExportImportManager(analytics_db=analytics_db, history_file=history_file)

    assert manager.analytics_db == analytics_db
    assert manager.history_file == history_file


def test_export_json(temp_dir, sample_analytics_data, sample_history_data):
    """Test exporting data to JSON"""
    analytics_db = temp_dir / "analytics.db"
    history_file = temp_dir / "history.json"
    output_file = temp_dir / "export.json"

    # Create test data
    with open(history_file, "w") as f:
        json.dump(sample_history_data, f)

    manager = ExportImportManager(analytics_db=analytics_db, history_file=history_file)

    # Export only history (analytics DB doesn't exist)
    result = manager.export_data(output_file, data_type="history", format="json")

    assert result["success"] is True
    assert result["history_count"] == 2
    assert output_file.exists()

    # Verify content
    with open(output_file) as f:
        data = json.load(f)
        assert "history" in data
        assert data["history"]["count"] == 2
        assert len(data["history"]["records"]) == 2


def test_export_csv(temp_dir, sample_history_data):
    """Test exporting data to CSV"""
    history_file = temp_dir / "history.json"
    output_file = temp_dir / "export.csv"

    # Create test data
    with open(history_file, "w") as f:
        json.dump(sample_history_data, f)

    manager = ExportImportManager(history_file=history_file)

    # Export to CSV
    result = manager.export_data(output_file, data_type="history", format="csv")

    assert result["success"] is True
    assert output_file.exists()

    # Verify CSV content
    import csv

    with open(output_file, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "hist1"
        assert rows[0]["domain"] == "education"


def test_export_with_date_filter(temp_dir, sample_history_data):
    """Test exporting with date filters"""
    history_file = temp_dir / "history.json"
    output_file = temp_dir / "export.json"

    # Create test data
    with open(history_file, "w") as f:
        json.dump(sample_history_data, f)

    manager = ExportImportManager(history_file=history_file)

    # Export with start date filter
    result = manager.export_data(
        output_file, data_type="history", format="json", start_date="2025-10-07T10:30:00"
    )

    assert result["success"] is True

    with open(output_file) as f:
        data = json.load(f)
        # Should only get records after 10:30
        assert data["history"]["count"] == 1
        assert data["history"]["records"][0]["id"] == "hist2"


def test_import_json(temp_dir):
    """Test importing data from JSON"""
    history_file = temp_dir / "history.json"
    import_file = temp_dir / "import.json"

    # Create import data
    import_data = {
        "export_date": "2025-10-07T12:00:00",
        "version": "2.0.13",
        "data_type": "history",
        "history": {
            "count": 2,
            "records": [
                {
                    "id": "import1",
                    "timestamp": "2025-10-07T09:00:00",
                    "prompt_text": "Imported prompt",
                    "prompt_hash": "imp123",
                    "domain": "general",
                    "language": "en",
                    "score": 90.0,
                    "ir_version": "v2",
                    "tags": [],
                }
            ],
        },
    }

    with open(import_file, "w") as f:
        json.dump(import_data, f)

    manager = ExportImportManager(history_file=history_file)

    # Import data
    result = manager.import_data(import_file, data_type="history", merge=False)

    assert result["success"] is True
    assert result["history_imported"] == 1
    assert history_file.exists()

    # Verify imported data
    with open(history_file) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "import1"


def test_import_merge_mode(temp_dir):
    """Test importing with merge mode"""
    history_file = temp_dir / "history.json"
    import_file = temp_dir / "import.json"

    # Create existing data
    existing_data = [
        {
            "id": "existing1",
            "timestamp": "2025-10-07T08:00:00",
            "prompt_text": "Existing prompt",
            "prompt_hash": "exist123",
            "domain": "general",
            "language": "en",
            "score": 80.0,
            "ir_version": "v2",
            "tags": [],
        }
    ]

    with open(history_file, "w") as f:
        json.dump(existing_data, f)

    # Create import data
    import_data = {
        "export_date": "2025-10-07T12:00:00",
        "version": "2.0.13",
        "data_type": "history",
        "history": {
            "count": 1,
            "records": [
                {
                    "id": "import1",
                    "timestamp": "2025-10-07T09:00:00",
                    "prompt_text": "Imported prompt",
                    "prompt_hash": "imp123",
                    "domain": "general",
                    "language": "en",
                    "score": 90.0,
                    "ir_version": "v2",
                    "tags": [],
                }
            ],
        },
    }

    with open(import_file, "w") as f:
        json.dump(import_data, f)

    manager = ExportImportManager(history_file=history_file)

    # Import with merge
    result = manager.import_data(import_file, data_type="history", merge=True)

    assert result["success"] is True

    # Verify both entries exist
    with open(history_file) as f:
        data = json.load(f)
        assert len(data) == 2
        hashes = [e["prompt_hash"] for e in data]
        assert "exist123" in hashes
        assert "imp123" in hashes


def test_import_csv(temp_dir):
    """Test importing data from CSV"""
    history_file = temp_dir / "history.json"
    import_file = temp_dir / "import.csv"

    # Create CSV data
    import csv

    with open(import_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "timestamp", "prompt_text", "prompt_hash", "domain", "language", "score", "ir_version", "tags"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "csv1",
                "timestamp": "2025-10-07T10:00:00",
                "prompt_text": "CSV imported",
                "prompt_hash": "csv123",
                "domain": "general",
                "language": "en",
                "score": "85.0",
                "ir_version": "v2",
                "tags": "test,csv",
            }
        )

    manager = ExportImportManager(history_file=history_file)

    # Import CSV
    result = manager.import_data(import_file, data_type="history", merge=False)

    assert result["success"] is True
    assert result["history_imported"] == 1

    # Verify imported data
    with open(history_file) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "csv1"
        assert data[0]["tags"] == ["test", "csv"]


def test_detect_format(temp_dir):
    """Test format detection from file extension"""
    manager = ExportImportManager()

    assert manager._detect_format(Path("file.json")) == "json"
    assert manager._detect_format(Path("file.csv")) == "csv"
    assert manager._detect_format(Path("file.yaml")) == "yaml"
    assert manager._detect_format(Path("file.yml")) == "yaml"

    with pytest.raises(ValueError):
        manager._detect_format(Path("file.txt"))


def test_export_both_csv_creates_separate_files(temp_dir, sample_history_data):
    """Test that exporting both data types as CSV creates separate files"""
    history_file = temp_dir / "history.json"
    output_file = temp_dir / "export.csv"

    # Create test data
    with open(history_file, "w") as f:
        json.dump(sample_history_data, f)

    manager = ExportImportManager(history_file=history_file)

    # Export both as CSV
    result = manager.export_data(output_file, data_type="both", format="csv")

    assert result["success"] is True

    # Check for separate files
    analytics_file = temp_dir / "export_analytics.csv"
    history_csv = temp_dir / "export_history.csv"

    # Only history file should exist (no analytics data)
    assert history_csv.exists()


def test_import_analytics_creates_database(temp_dir):
    """Test that importing analytics creates SQLite database"""
    analytics_db = temp_dir / "analytics.db"
    import_file = temp_dir / "import.json"

    # Create import data with analytics
    import_data = {
        "export_date": "2025-10-07T12:00:00",
        "version": "2.0.13",
        "data_type": "analytics",
        "analytics": {
            "count": 1,
            "records": [
                {
                    "timestamp": "2025-10-07T10:00:00",
                    "prompt_text": "Test prompt",
                    "prompt_hash": "test123",
                    "validation_score": 85.0,
                    "domain": "general",
                    "persona": "assistant",
                    "language": "en",
                    "intents": ["explain"],
                    "issues_count": 1,
                    "warnings_count": 0,
                    "prompt_length": 11,
                    "ir_version": "v2",
                    "tags": [],
                }
            ],
        },
    }

    with open(import_file, "w") as f:
        json.dump(import_data, f)

    manager = ExportImportManager(analytics_db=analytics_db)

    # Import analytics
    result = manager.import_data(import_file, data_type="analytics", merge=False)

    assert result["success"] is True
    assert result["analytics_imported"] == 1
    assert analytics_db.exists()

    # Verify database content
    import sqlite3

    conn = sqlite3.connect(analytics_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM prompts")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 1


def test_empty_export(temp_dir):
    """Test exporting when no data exists"""
    analytics_db = temp_dir / "analytics.db"
    history_file = temp_dir / "history.json"
    output_file = temp_dir / "export.json"

    manager = ExportImportManager(analytics_db=analytics_db, history_file=history_file)

    # Export when no data exists
    result = manager.export_data(output_file, data_type="both", format="json")

    assert result["success"] is True
    assert result["analytics_count"] == 0
    assert result["history_count"] == 0
    assert output_file.exists()
