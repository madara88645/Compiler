"""Search history manager for tracking recent searches."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class SearchHistoryEntry:
    """Single search history entry."""

    query: str
    result_count: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    types_filter: Optional[List[str]] = None
    min_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchHistoryEntry":
        """Create from dictionary."""
        return cls(**data)


class SearchHistoryManager:
    """Manages search history with persistence."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize with storage path."""
        if storage_path is None:
            storage_path = Path.home() / ".promptc" / "search_history.json"
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: List[SearchHistoryEntry] = []
        self._load()

    def _load(self):
        """Load history from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._entries = [
                        SearchHistoryEntry.from_dict(entry) for entry in data
                    ]
            except Exception:
                self._entries = []

    def _save(self):
        """Save history to storage."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    [entry.to_dict() for entry in self._entries],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception:
            pass

    def add(
        self,
        query: str,
        result_count: int,
        types_filter: Optional[List[str]] = None,
        min_score: float = 0.0,
    ):
        """Add a search to history."""
        entry = SearchHistoryEntry(
            query=query,
            result_count=result_count,
            types_filter=types_filter,
            min_score=min_score,
        )
        self._entries.insert(0, entry)  # Add to front

        # Keep only last 10 searches
        if len(self._entries) > 10:
            self._entries = self._entries[:10]

        self._save()

    def get_recent(self, limit: int = 10) -> List[SearchHistoryEntry]:
        """Get recent searches."""
        return self._entries[:limit]

    def clear(self):
        """Clear all history."""
        self._entries = []
        self._save()

    def get_by_index(self, index: int) -> Optional[SearchHistoryEntry]:
        """Get search by index (0-based)."""
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None


# Singleton instance
_search_history_manager = None


def get_search_history_manager() -> SearchHistoryManager:
    """Get the singleton search history manager."""
    global _search_history_manager
    if _search_history_manager is None:
        _search_history_manager = SearchHistoryManager()
    return _search_history_manager
