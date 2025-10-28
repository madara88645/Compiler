"""
Export/Import Module

Allows exporting and importing prompts, favorites, and history data in various formats.
Supports JSON and CSV formats for data portability, backup, and migration.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from rich.console import Console
from rich.panel import Panel

from app.history import get_history_manager
from app.favorites import get_favorites_manager


FormatType = Literal["json", "csv"]
DataType = Literal["history", "favorites", "all"]


console = Console()


class ExportImportManager:
    """Manages export and import operations for prompts, favorites, and history"""

    def __init__(self):
        """Initialize export/import manager with history and favorites managers"""
        self.history_manager = get_history_manager()
        self.favorites_manager = get_favorites_manager()

    def export_to_json(
        self,
        output_path: Path,
        source: DataType = "all",
        pretty: bool = True,
    ) -> Dict[str, Any]:
        """Export prompt data to JSON format.

        Args:
            output_path: Path to save the JSON file
            source: Source to export from ("history", "favorites", "all")
            pretty: Whether to use pretty printing (indented JSON)

        Returns:
            Dictionary with export statistics
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "version": "2.0.33",
            "source": source,
            "data": {}
        }

        stats = {"history": 0, "favorites": 0, "total": 0}

        if source in ["history", "all"]:
            history_data = self.history_manager.load_history()
            data["data"]["history"] = history_data
            stats["history"] = len(history_data)

        if source in ["favorites", "all"]:
            favorites_data = self.favorites_manager.load_favorites()
            data["data"]["favorites"] = favorites_data
            stats["favorites"] = len(favorites_data)

        stats["total"] = stats["history"] + stats["favorites"]

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        return stats

    def export_to_csv(
        self,
        output_path: Path,
        source: DataType = "all",
    ) -> Dict[str, Any]:
        """Export prompt data to CSV format.

        Args:
            output_path: Path to save the CSV file
            source: Source to export from ("history", "favorites", "all")

        Returns:
            Dictionary with export statistics
        """
        stats = {"history": 0, "favorites": 0, "total": 0}
        rows = []

        # Collect data from history
        if source in ["history", "all"]:
            history_data = self.history_manager.load_history()
            for item in history_data:
                row = self._flatten_item(item, source_type="history")
                rows.append(row)
            stats["history"] = len(history_data)

        # Collect data from favorites
        if source in ["favorites", "all"]:
            favorites_data = self.favorites_manager.load_favorites()
            for item in favorites_data:
                row = self._flatten_item(item, source_type="favorites")
                rows.append(row)
            stats["favorites"] = len(favorites_data)

        stats["total"] = len(rows)

        # Write to CSV
        if rows:
            fieldnames = list(rows[0].keys())
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        return stats

    def _flatten_item(self, item: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Flatten a prompt item for CSV export.

        Args:
            item: Prompt item dictionary
            source_type: "history" or "favorites"

        Returns:
            Flattened dictionary suitable for CSV
        """
        flat = {
            "source": source_type,
            "id": item.get("id", ""),
            "timestamp": item.get("timestamp", ""),
            "input_text": item.get("input_text", ""),
            "output_prompt": item.get("output_prompt", ""),
            "domain": item.get("domain", ""),
            "language": item.get("language", ""),
            "persona": item.get("persona", ""),
            "teaching_level": item.get("teaching_level", ""),
            "duration": item.get("duration", ""),
            "score": item.get("score", ""),
            "tags": ",".join(item.get("tags", [])) if item.get("tags") else "",
            "note": item.get("note", ""),
        }

        # Add favorites-specific fields
        if source_type == "favorites":
            flat["added_date"] = item.get("added_date", "")
            flat["use_count"] = item.get("use_count", 0)

        return flat

    def import_from_json(
        self,
        input_path: Path,
        target: DataType = "auto",
        merge: bool = True,
    ) -> Dict[str, Any]:
        """Import prompt data from JSON format.

        Args:
            input_path: Path to the JSON file
            target: Target to import to ("history", "favorites", "auto")
            merge: Whether to merge with existing data (True) or replace (False)

        Returns:
            Dictionary with import statistics
        """
        stats = {"history": 0, "favorites": 0, "total": 0, "skipped": 0}

        # Load JSON data
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different JSON structures
        import_data = data.get("data", data)

        # Import history
        if target in ["history", "auto"] and "history" in import_data:
            history_items = import_data["history"]
            if not merge:
                self.history_manager.history = []

            existing_ids = {item.get("id") for item in self.history_manager.load_history()}

            imported = 0
            for item in history_items:
                if item.get("id") not in existing_ids:
                    self.history_manager.history.append(item)
                    imported += 1
                else:
                    stats["skipped"] += 1

            self.history_manager.save_history()
            stats["history"] = imported

        # Import favorites
        if target in ["favorites", "auto"] and "favorites" in import_data:
            favorites_items = import_data["favorites"]
            if not merge:
                self.favorites_manager.favorites = []

            existing_ids = {item.get("id") for item in self.favorites_manager.load_favorites()}

            imported = 0
            for item in favorites_items:
                if item.get("id") not in existing_ids:
                    self.favorites_manager.favorites.append(item)
                    imported += 1
                else:
                    stats["skipped"] += 1

            self.favorites_manager.save_favorites()
            stats["favorites"] = imported

        stats["total"] = stats["history"] + stats["favorites"]
        return stats

    def import_from_csv(
        self,
        input_path: Path,
        target: DataType = "auto",
        merge: bool = True,
    ) -> Dict[str, Any]:
        """Import prompt data from CSV format.

        Args:
            input_path: Path to the CSV file
            target: Target to import to ("history", "favorites", "auto")
            merge: Whether to merge with existing data (True) or replace (False)

        Returns:
            Dictionary with import statistics
        """
        stats = {"history": 0, "favorites": 0, "total": 0, "skipped": 0}

        # Read CSV data
        with open(input_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not merge:
            if target in ["history", "auto"]:
                self.history_manager.history = []
            if target in ["favorites", "auto"]:
                self.favorites_manager.favorites = []

        # Get existing IDs
        existing_history_ids = {item.get("id") for item in self.history_manager.load_history()}
        existing_favorites_ids = {
            item.get("id") for item in self.favorites_manager.load_favorites()
        }

        # Process rows
        for row in rows:
            item = self._unflatten_item(row)
            source_type = row.get("source", target if target != "auto" else "history")

            # Determine target based on source field or target parameter
            if target == "auto":
                actual_target = source_type
            else:
                actual_target = target

            # Import to history
            if actual_target == "history":
                if item.get("id") not in existing_history_ids:
                    self.history_manager.history.append(item)
                    existing_history_ids.add(item.get("id"))
                    stats["history"] += 1
                else:
                    stats["skipped"] += 1

            # Import to favorites
            elif actual_target == "favorites":
                if item.get("id") not in existing_favorites_ids:
                    self.favorites_manager.favorites.append(item)
                    existing_favorites_ids.add(item.get("id"))
                    stats["favorites"] += 1
                else:
                    stats["skipped"] += 1

        # Save changes
        if stats["history"] > 0:
            self.history_manager.save_history()
        if stats["favorites"] > 0:
            self.favorites_manager.save_favorites()

        stats["total"] = stats["history"] + stats["favorites"]
        return stats

    def _unflatten_item(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Unflatten a CSV row back to prompt item format.

        Args:
            row: CSV row as dictionary

        Returns:
            Prompt item dictionary
        """
        item = {
            "id": row.get("id", ""),
            "timestamp": row.get("timestamp", ""),
            "input_text": row.get("input_text", ""),
            "output_prompt": row.get("output_prompt", ""),
            "domain": row.get("domain", ""),
            "language": row.get("language", ""),
            "persona": row.get("persona", ""),
            "teaching_level": row.get("teaching_level", ""),
            "duration": row.get("duration", ""),
        }

        # Handle optional fields
        if row.get("score"):
            try:
                item["score"] = float(row["score"])
            except (ValueError, TypeError):
                pass

        if row.get("tags"):
            item["tags"] = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]

        if row.get("note"):
            item["note"] = row["note"]

        # Add favorites-specific fields
        if row.get("added_date"):
            item["added_date"] = row["added_date"]

        if row.get("use_count"):
            try:
                item["use_count"] = int(row["use_count"])
            except (ValueError, TypeError):
                item["use_count"] = 0

        return item

    def display_export_summary(self, stats: Dict[str, Any], format_type: str, output_path: Path):
        """Display a summary of the export operation.

        Args:
            stats: Export statistics
            format_type: Format used ("json" or "csv")
            output_path: Path where file was saved
        """
        console.print()
        console.print(Panel.fit(
            f"[bold green]✅ Export Successful[/bold green]\n\n"
            f"[cyan]Format:[/cyan] {format_type.upper()}\n"
            f"[cyan]Location:[/cyan] {output_path}\n"
            f"[cyan]File Size:[/cyan] {output_path.stat().st_size:,} bytes\n\n"
            f"[yellow]Exported Items:[/yellow]\n"
            f"  • History: {stats['history']}\n"
            f"  • Favorites: {stats['favorites']}\n"
            f"  • Total: {stats['total']}",
            border_style="green",
            title="📦 Export Complete"
        ))

    def display_import_summary(self, stats: Dict[str, Any], format_type: str, merge: bool):
        """Display a summary of the import operation.

        Args:
            stats: Import statistics
            format_type: Format used ("json" or "csv")
            merge: Whether data was merged or replaced
        """
        mode = "Merged" if merge else "Replaced"

        console.print()
        console.print(Panel.fit(
            f"[bold green]✅ Import Successful[/bold green]\n\n"
            f"[cyan]Format:[/cyan] {format_type.upper()}\n"
            f"[cyan]Mode:[/cyan] {mode}\n\n"
            f"[yellow]Imported Items:[/yellow]\n"
            f"  • History: {stats['history']}\n"
            f"  • Favorites: {stats['favorites']}\n"
            f"  • Total: {stats['total']}\n"
            f"  • Skipped (duplicates): {stats['skipped']}",
            border_style="green",
            title="📥 Import Complete"
        ))


# Singleton instance
_export_import_manager: Optional[ExportImportManager] = None


def get_export_import_manager() -> ExportImportManager:
    """Get or create the singleton ExportImportManager instance.

    Returns:
        ExportImportManager instance
    """
    global _export_import_manager
    if _export_import_manager is None:
        _export_import_manager = ExportImportManager()
    return _export_import_manager
