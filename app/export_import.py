"""
Export/Import Module

Allows exporting and importing analytics and history data in various formats.
Supports JSON, CSV, and YAML formats for data portability and backup.
"""

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


FormatType = Literal["json", "csv", "yaml"]
DataType = Literal["analytics", "history", "both"]


class ExportImportManager:
    """Manages export and import operations for analytics and history data"""

    def __init__(self, analytics_db: Optional[Path] = None, history_file: Optional[Path] = None):
        """
        Initialize export/import manager

        Args:
            analytics_db: Path to analytics SQLite database
            history_file: Path to history JSON file
        """
        if analytics_db is None:
            analytics_db = Path.home() / ".promptc" / "analytics.db"
        if history_file is None:
            history_file = Path.home() / ".promptc" / "history.json"

        self.analytics_db = analytics_db
        self.history_file = history_file

    def export_data(
        self,
        output_file: Path,
        data_type: DataType = "both",
        format: FormatType = "json",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export analytics and/or history data

        Args:
            output_file: Output file path
            data_type: What to export (analytics, history, or both)
            format: Export format (json, csv, yaml)
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)

        Returns:
            Export summary with counts and file info
        """
        if format == "yaml" and not HAS_YAML:
            raise ImportError("YAML support requires pyyaml: pip install pyyaml")

        export_data: Dict[str, Any] = {
            "export_date": datetime.now().isoformat(),
            "version": "2.0.13",
            "data_type": data_type,
        }

        # Export analytics
        if data_type in ("analytics", "both"):
            analytics_records = self._export_analytics(start_date, end_date)
            export_data["analytics"] = {
                "count": len(analytics_records),
                "records": analytics_records,
            }

        # Export history
        if data_type in ("history", "both"):
            history_records = self._export_history(start_date, end_date)
            export_data["history"] = {
                "count": len(history_records),
                "records": history_records,
            }

        # Write to file based on format
        if format == "json":
            self._write_json(output_file, export_data)
        elif format == "csv":
            self._write_csv(output_file, export_data, data_type)
        elif format == "yaml":
            self._write_yaml(output_file, export_data)

        return {
            "success": True,
            "file": str(output_file),
            "format": format,
            "data_type": data_type,
            "analytics_count": export_data.get("analytics", {}).get("count", 0),
            "history_count": export_data.get("history", {}).get("count", 0),
            "export_date": export_data["export_date"],
        }

    def import_data(
        self, input_file: Path, data_type: DataType = "both", merge: bool = True
    ) -> Dict[str, Any]:
        """
        Import analytics and/or history data

        Args:
            input_file: Input file path
            data_type: What to import (analytics, history, or both)
            merge: If True, merge with existing data; if False, replace

        Returns:
            Import summary with counts
        """
        # Detect format from extension
        format = self._detect_format(input_file)

        # Read data based on format
        if format == "json":
            import_data = self._read_json(input_file)
        elif format == "csv":
            import_data = self._read_csv(input_file, data_type)
        elif format == "yaml":
            import_data = self._read_yaml(input_file)
        else:
            raise ValueError(f"Unsupported format: {format}")

        summary = {
            "success": True,
            "file": str(input_file),
            "format": format,
            "merge_mode": merge,
            "analytics_imported": 0,
            "history_imported": 0,
        }

        # Import analytics
        if data_type in ("analytics", "both") and "analytics" in import_data:
            count = self._import_analytics(import_data["analytics"]["records"], merge)
            summary["analytics_imported"] = count

        # Import history
        if data_type in ("history", "both") and "history" in import_data:
            count = self._import_history(import_data["history"]["records"], merge)
            summary["history_imported"] = count

        return summary

    def _export_analytics(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Export analytics records from SQLite database"""
        if not self.analytics_db.exists():
            return []

        conn = sqlite3.connect(self.analytics_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompts'")
        if not cursor.fetchone():
            conn.close()
            return []

        query = "SELECT * FROM prompts"
        params = []

        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)
            query += " WHERE " + " AND ".join(conditions)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        records = []
        for row in rows:
            record = dict(row)
            # Parse JSON fields
            if record.get("intents"):
                record["intents"] = json.loads(record["intents"])
            if record.get("tags"):
                record["tags"] = json.loads(record["tags"])
            records.append(record)

        return records

    def _export_history(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Export history records from JSON file"""
        if not self.history_file.exists():
            return []

        with open(self.history_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        # Filter by date if specified
        if start_date or end_date:
            filtered = []
            for record in records:
                timestamp = record.get("timestamp", "")
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered.append(record)
            return filtered

        return records

    def _import_analytics(self, records: List[Dict[str, Any]], merge: bool) -> int:
        """Import analytics records into SQLite database"""
        # Ensure database exists
        self.analytics_db.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.analytics_db)
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                prompt_text TEXT,
                prompt_hash TEXT UNIQUE,
                validation_score REAL,
                domain TEXT,
                persona TEXT,
                language TEXT,
                intents TEXT,
                issues_count INTEGER,
                warnings_count INTEGER,
                prompt_length INTEGER,
                ir_version TEXT,
                tags TEXT
            )
        """)

        if not merge:
            # Clear existing data
            cursor.execute("DELETE FROM prompts")

        # Insert records
        imported = 0
        for record in records:
            # Serialize JSON fields
            intents = json.dumps(record.get("intents", []))
            tags = json.dumps(record.get("tags", []))

            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO prompts
                    (timestamp, prompt_text, prompt_hash, validation_score, domain,
                     persona, language, intents, issues_count, warnings_count,
                     prompt_length, ir_version, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        record.get("timestamp"),
                        record.get("prompt_text"),
                        record.get("prompt_hash"),
                        record.get("validation_score"),
                        record.get("domain"),
                        record.get("persona"),
                        record.get("language"),
                        intents,
                        record.get("issues_count"),
                        record.get("warnings_count"),
                        record.get("prompt_length"),
                        record.get("ir_version"),
                        tags,
                    ),
                )
                imported += 1
            except sqlite3.IntegrityError:
                # Duplicate entry, skip
                pass

        conn.commit()
        conn.close()

        return imported

    def _import_history(self, records: List[Dict[str, Any]], merge: bool) -> int:
        """Import history records into JSON file"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        existing_records = []
        if merge and self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                existing_records = json.load(f)

        # Merge or replace
        if merge:
            # Use dict to deduplicate by hash
            combined = {r.get("prompt_hash"): r for r in existing_records}
            for record in records:
                combined[record.get("prompt_hash")] = record
            final_records = list(combined.values())
        else:
            final_records = records

        # Sort by timestamp
        final_records.sort(key=lambda x: x.get("timestamp", ""))

        # Keep only last 100
        final_records = final_records[-100:]

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(final_records, f, ensure_ascii=False, indent=2)

        return len(records)

    def _write_json(self, output_file: Path, data: Dict[str, Any]):
        """Write data as JSON"""
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _write_csv(self, output_file: Path, data: Dict[str, Any], data_type: DataType):
        """Write data as CSV"""
        if data_type == "both":
            # Create separate CSV files for analytics and history
            base = output_file.stem
            parent = output_file.parent

            if "analytics" in data:
                analytics_file = parent / f"{base}_analytics.csv"
                self._write_csv_records(analytics_file, data["analytics"]["records"], "analytics")

            if "history" in data:
                history_file = parent / f"{base}_history.csv"
                self._write_csv_records(history_file, data["history"]["records"], "history")
        else:
            # Single CSV file
            records = data.get(data_type, {}).get("records", [])
            self._write_csv_records(output_file, records, data_type)

    def _write_csv_records(self, output_file: Path, records: List[Dict], data_type: str):
        """Write records to CSV file"""
        if not records:
            return

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            # Flatten nested fields for CSV
            flattened = []
            for record in records:
                flat = record.copy()
                # Convert lists to comma-separated strings
                for key, value in flat.items():
                    if isinstance(value, list):
                        flat[key] = ",".join(str(v) for v in value)
                flattened.append(flat)

            writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
            writer.writeheader()
            writer.writerows(flattened)

    def _write_yaml(self, output_file: Path, data: Dict[str, Any]):
        """Write data as YAML"""
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def _read_json(self, input_file: Path) -> Dict[str, Any]:
        """Read data from JSON"""
        with open(input_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_csv(self, input_file: Path, data_type: DataType) -> Dict[str, Any]:
        """Read data from CSV"""
        result: Dict[str, Any] = {
            "export_date": datetime.now().isoformat(),
            "version": "2.0.13",
            "data_type": data_type,
        }

        if data_type == "both":
            # Look for separate CSV files
            base = input_file.stem
            parent = input_file.parent

            analytics_file = parent / f"{base}_analytics.csv"
            if analytics_file.exists():
                records = self._read_csv_records(analytics_file)
                result["analytics"] = {"count": len(records), "records": records}

            history_file = parent / f"{base}_history.csv"
            if history_file.exists():
                records = self._read_csv_records(history_file)
                result["history"] = {"count": len(records), "records": records}
        else:
            records = self._read_csv_records(input_file)
            result[data_type] = {"count": len(records), "records": records}

        return result

    def _read_csv_records(self, input_file: Path) -> List[Dict[str, Any]]:
        """Read records from CSV file"""
        records = []
        with open(input_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse comma-separated fields back to lists
                record = {}
                for key, value in row.items():
                    if key in ("intents", "tags") and value:
                        record[key] = value.split(",")
                    else:
                        record[key] = value
                records.append(record)
        return records

    def _read_yaml(self, input_file: Path) -> Dict[str, Any]:
        """Read data from YAML"""
        with open(input_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _detect_format(self, file_path: Path) -> FormatType:
        """Detect file format from extension"""
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return "json"
        elif suffix == ".csv":
            return "csv"
        elif suffix in (".yaml", ".yml"):
            return "yaml"
        else:
            raise ValueError(f"Unknown file format: {suffix}")


def get_export_import_manager() -> ExportImportManager:
    """Get or create export/import manager instance"""
    return ExportImportManager()
