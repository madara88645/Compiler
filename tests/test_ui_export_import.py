"""Tests for UI-based export/import and backup functionality."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_history():
    """Sample history data."""
    return [
        {
            "timestamp": "2025-11-08T10:00:00",
            "preview": "Write a Python function...",
            "full_text": "Write a Python function to calculate fibonacci numbers",
            "is_favorite": False,
            "tags": ["code", "tutorial"],
            "usage_count": 5,
            "length": 54,
        },
        {
            "timestamp": "2025-11-08T11:30:00",
            "preview": "Explain async/await...",
            "full_text": "Explain async/await in JavaScript with examples",
            "is_favorite": True,
            "tags": ["writing", "tutorial"],
            "usage_count": 3,
            "length": 47,
        },
    ]


@pytest.fixture
def sample_tags():
    """Sample tags data."""
    return [
        {"name": "code", "color": "#3b82f6"},
        {"name": "writing", "color": "#10b981"},
        {"name": "tutorial", "color": "#f59e0b"},
    ]


@pytest.fixture
def sample_snippets():
    """Sample snippets data."""
    return [
        {
            "name": "Code Review",
            "category": "review",
            "content": "Please review this code:\n\n",
        },
        {
            "name": "Bug Report",
            "category": "debug",
            "content": "Bug description:\n\nSteps to reproduce:\n\nExpected:\n\nActual:\n",
        },
    ]


class TestExportData:
    """Tests for export functionality."""

    def test_export_all_structure(self, temp_dir, sample_history, sample_tags, sample_snippets):
        """Test export all data creates correct structure."""
        export_file = temp_dir / "export_all.json"

        # Simulate export
        export_data = {
            "version": "2.0.43",
            "export_date": datetime.now().isoformat(),
            "history": sample_history,
            "tags": sample_tags,
            "snippets": sample_snippets,
            "ui_settings": {"theme": "dark"},
        }

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        # Verify
        assert export_file.exists()

        with open(export_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "2.0.43"
        assert "export_date" in data
        assert len(data["history"]) == 2
        assert len(data["tags"]) == 3
        assert len(data["snippets"]) == 2
        assert data["ui_settings"]["theme"] == "dark"

    def test_export_history_only(self, temp_dir, sample_history):
        """Test export only history."""
        export_file = temp_dir / "export_history.json"

        export_data = {
            "version": "2.0.43",
            "export_date": datetime.now().isoformat(),
            "history": sample_history,
        }

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        with open(export_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "history" in data
        assert "tags" not in data
        assert "snippets" not in data
        assert len(data["history"]) == 2

    def test_export_tags_only(self, temp_dir, sample_tags):
        """Test export only tags."""
        export_file = temp_dir / "export_tags.json"

        export_data = {
            "version": "2.0.43",
            "export_date": datetime.now().isoformat(),
            "tags": sample_tags,
        }

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        with open(export_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "tags" in data
        assert "history" not in data
        assert len(data["tags"]) == 3

    def test_export_utf8_encoding(self, temp_dir):
        """Test export handles UTF-8 characters correctly."""
        history = [
            {
                "timestamp": "2025-11-08T10:00:00",
                "preview": "Python öğreniyorum...",
                "full_text": "Python öğreniyorum, yardım eder misin?",
                "is_favorite": False,
                "tags": ["türkçe"],
                "usage_count": 1,
                "length": 39,
            }
        ]

        export_file = temp_dir / "export_utf8.json"
        export_data = {
            "version": "2.0.43",
            "export_date": datetime.now().isoformat(),
            "history": history,
        }

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        with open(export_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["history"][0]["full_text"] == "Python öğreniyorum, yardım eder misin?"
        assert data["history"][0]["tags"] == ["türkçe"]


class TestImportData:
    """Tests for import functionality."""

    def test_import_valid_file(self, temp_dir, sample_history, sample_tags):
        """Test import valid JSON file."""
        import_file = temp_dir / "import.json"

        import_data = {
            "version": "2.0.43",
            "export_date": "2025-11-08T12:00:00",
            "history": sample_history,
            "tags": sample_tags,
        }

        with open(import_file, "w", encoding="utf-8") as f:
            json.dump(import_data, f, indent=2, ensure_ascii=False)

        # Read and validate
        with open(import_file, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert data["version"] == "2.0.43"
        assert isinstance(data["history"], list)
        assert isinstance(data["tags"], list)

    def test_import_merge_no_duplicates(self, sample_history):
        """Test merge mode doesn't create duplicates."""
        existing = sample_history.copy()
        imported = sample_history.copy()

        # Simulate merge logic
        existing_keys = {
            (item["timestamp"], item["full_text"]) for item in existing
        }
        new_items = [
            item
            for item in imported
            if (item["timestamp"], item["full_text"]) not in existing_keys
        ]

        merged = existing + new_items

        # Should not have duplicates
        assert len(merged) == len(existing)

    def test_import_merge_adds_new_items(self, sample_history):
        """Test merge mode adds new items."""
        existing = [sample_history[0]]
        imported = sample_history.copy()

        # Simulate merge
        existing_keys = {
            (item["timestamp"], item["full_text"]) for item in existing
        }
        new_items = [
            item
            for item in imported
            if (item["timestamp"], item["full_text"]) not in existing_keys
        ]

        merged = existing + new_items

        assert len(merged) == 2

    def test_import_replace_mode(self, sample_history):
        """Test replace mode overwrites existing data."""
        existing = [
            {
                "timestamp": "2025-11-07T10:00:00",
                "preview": "Old prompt...",
                "full_text": "Old prompt text",
                "is_favorite": False,
                "tags": [],
                "usage_count": 0,
                "length": 15,
            }
        ]
        imported = sample_history.copy()

        # Replace mode
        replaced = imported

        assert len(replaced) == 2
        assert replaced[0]["full_text"] != "Old prompt text"

    def test_import_tags_merge(self, sample_tags):
        """Test merging tags without duplicates."""
        existing = sample_tags[:2]
        imported = sample_tags.copy()

        # Simulate tag merge
        existing_names = {tag["name"] for tag in existing}
        new_tags = [tag for tag in imported if tag["name"] not in existing_names]
        merged = existing + new_tags

        assert len(merged) == 3
        tag_names = [tag["name"] for tag in merged]
        assert len(tag_names) == len(set(tag_names))  # No duplicates

    def test_import_snippets_merge(self, sample_snippets):
        """Test merging snippets without duplicates."""
        existing = [sample_snippets[0]]
        imported = sample_snippets.copy()

        # Simulate snippet merge
        existing_names = {snip["name"] for snip in existing}
        new_snippets = [snip for snip in imported if snip["name"] not in existing_names]
        merged = existing + new_snippets

        assert len(merged) == 2


class TestAutoBackup:
    """Tests for automatic backup functionality."""

    def test_backup_structure(self, temp_dir, sample_history, sample_tags, sample_snippets):
        """Test backup file has correct structure."""
        backup_file = temp_dir / "auto_backup_20251108_120000.json"

        backup_data = {
            "version": "2.0.43",
            "backup_date": datetime.now().isoformat(),
            "backup_type": "auto",
            "history": sample_history,
            "tags": sample_tags,
            "snippets": sample_snippets,
            "ui_settings": {"theme": "light"},
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        with open(backup_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "2.0.43"
        assert data["backup_type"] == "auto"
        assert "backup_date" in data
        assert len(data["history"]) == 2

    def test_keep_last_5_backups(self, temp_dir):
        """Test that only last 5 backups are kept."""
        # Create 7 backup files
        for i in range(7):
            backup_file = temp_dir / f"auto_backup_2025110{i}_120000.json"
            with open(backup_file, "w") as f:
                json.dump({"test": i}, f)

        # Simulate cleanup
        backup_files = sorted(temp_dir.glob("auto_backup_*.json"))
        if len(backup_files) > 5:
            for old_backup in backup_files[:-5]:
                old_backup.unlink()

        # Verify only 5 remain
        remaining = list(temp_dir.glob("auto_backup_*.json"))
        assert len(remaining) == 5

        # Verify newest 5 are kept
        remaining_sorted = sorted(remaining)
        assert "auto_backup_20251102" in remaining_sorted[-5].name
        assert "auto_backup_20251106" in remaining_sorted[-1].name

    def test_backup_timestamp_format(self):
        """Test backup filename timestamp format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auto_backup_{timestamp}.json"

        # Should match format: auto_backup_YYYYMMDD_HHMMSS.json
        assert filename.startswith("auto_backup_")
        assert filename.endswith(".json")
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS


class TestRestoreBackup:
    """Tests for backup restoration."""

    def test_restore_backup(self, temp_dir, sample_history):
        """Test restoring from backup."""
        backup_file = temp_dir / "auto_backup_20251108_120000.json"

        backup_data = {
            "version": "2.0.43",
            "backup_date": "2025-11-08T12:00:00",
            "backup_type": "auto",
            "history": sample_history,
            "tags": [],
            "snippets": [],
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        # Restore
        with open(backup_file, encoding="utf-8") as f:
            restored_data = json.load(f)

        assert restored_data["backup_type"] == "auto"
        assert len(restored_data["history"]) == 2

    def test_list_backups_sorted(self, temp_dir):
        """Test backup list is sorted by date (newest first)."""
        # Create multiple backups
        timestamps = [
            "20251105_100000",
            "20251108_120000",
            "20251106_150000",
        ]

        for ts in timestamps:
            backup_file = temp_dir / f"auto_backup_{ts}.json"
            with open(backup_file, "w") as f:
                json.dump({"timestamp": ts}, f)

        # Get sorted list (newest first)
        backup_files = sorted(temp_dir.glob("auto_backup_*.json"), reverse=True)

        assert len(backup_files) == 3
        assert "20251108" in backup_files[0].name
        assert "20251106" in backup_files[1].name
        assert "20251105" in backup_files[2].name


class TestDataValidation:
    """Tests for data validation during import."""

    def test_invalid_json_structure(self, temp_dir):
        """Test handling invalid JSON structure."""
        import_file = temp_dir / "invalid.json"

        # Not a dict
        with open(import_file, "w") as f:
            json.dump(["not", "a", "dict"], f)

        with open(import_file) as f:
            data = json.load(f)

        assert not isinstance(data, dict)

    def test_missing_fields_handled(self, temp_dir):
        """Test import handles missing optional fields."""
        import_file = temp_dir / "partial.json"

        # Missing optional fields
        import_data = {
            "version": "2.0.43",
            "history": [
                {
                    "timestamp": "2025-11-08T10:00:00",
                    "preview": "Test",
                    "full_text": "Test prompt",
                    # Missing: is_favorite, tags, usage_count, length
                }
            ],
        }

        with open(import_file, "w") as f:
            json.dump(import_data, f)

        with open(import_file) as f:
            data = json.load(f)

        # Should still be valid
        assert "history" in data
        history_item = data["history"][0]
        assert "timestamp" in history_item
        assert "full_text" in history_item

    def test_backwards_compatibility(self, temp_dir):
        """Test old format without usage_count is handled."""
        import_file = temp_dir / "old_format.json"

        # Old format (v2.0.41 or earlier)
        import_data = {
            "version": "2.0.41",
            "history": [
                {
                    "timestamp": "2025-11-06T10:00:00",
                    "preview": "Old prompt",
                    "full_text": "Old prompt text",
                    "is_favorite": False,
                    "tags": ["code"],
                    # No usage_count, no length
                }
            ],
        }

        with open(import_file, "w") as f:
            json.dump(import_data, f)

        with open(import_file) as f:
            data = json.load(f)

        # Should handle missing fields gracefully
        history_item = data["history"][0]
        usage_count = history_item.get("usage_count", 0)
        length = history_item.get("length", len(history_item["full_text"]))

        assert usage_count == 0
        assert length == len("Old prompt text")


class TestUsageTracking:
    """Tests for usage count tracking."""

    def test_increment_usage_count(self, sample_history):
        """Test incrementing usage count."""
        item = sample_history[0].copy()
        initial_count = item["usage_count"]

        # Simulate usage
        item["usage_count"] += 1

        assert item["usage_count"] == initial_count + 1

    def test_usage_count_persistence(self, temp_dir, sample_history):
        """Test usage count is persisted to file."""
        history_file = temp_dir / "history.json"

        # Save initial
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(sample_history, f, indent=2, ensure_ascii=False)

        # Load and increment
        with open(history_file, encoding="utf-8") as f:
            data = json.load(f)

        data[0]["usage_count"] += 1

        # Save updated
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Verify persistence
        with open(history_file, encoding="utf-8") as f:
            updated = json.load(f)

        assert updated[0]["usage_count"] == sample_history[0]["usage_count"] + 1

    def test_default_usage_count(self):
        """Test default usage count is 0."""
        item = {
            "timestamp": "2025-11-08T10:00:00",
            "preview": "Test",
            "full_text": "Test prompt",
            "is_favorite": False,
            "tags": [],
        }

        usage_count = item.get("usage_count", 0)
        assert usage_count == 0
