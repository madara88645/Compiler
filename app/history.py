"""
Prompt History Module

Keeps track of recent prompt compilations for quick access and reference.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class HistoryEntry:
    """Single history entry"""

    id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    prompt_text: str = ""
    prompt_hash: str = ""
    domain: str = "general"
    language: str = "en"
    score: float = 0.0
    ir_version: str = "v2"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        """Create from dictionary"""
        return cls(**data)


class HistoryManager:
    """Manages prompt history storage and retrieval"""

    def __init__(self, history_file: Optional[Path] = None, max_entries: int = 100):
        """
        Initialize history manager

        Args:
            history_file: Path to history JSON file. Defaults to ~/.promptc/history.json
            max_entries: Maximum number of entries to keep
        """
        if history_file is None:
            history_file = Path.home() / ".promptc" / "history.json"

        self.history_file = history_file
        self.max_entries = max_entries
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        self.entries: List[HistoryEntry] = []
        self._load()

    def _load(self):
        """Load history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [HistoryEntry.from_dict(e) for e in data]
            except Exception:
                # If file is corrupted, start fresh
                self.entries = []

    def _save(self):
        """Save history to file"""
        # Keep only max_entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        data = [e.to_dict() for e in self.entries]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, prompt_text: str, ir: Dict[str, Any], score: float = 0.0):
        """
        Add a new entry to history

        Args:
            prompt_text: The prompt text
            ir: Compiled IR dictionary
            score: Optional validation score
        """
        # Generate hash
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]

        # Create entry
        entry = HistoryEntry(
            id=prompt_hash,
            prompt_text=prompt_text[:500],  # Truncate for storage
            prompt_hash=prompt_hash,
            domain=ir.get("domain", "general"),
            language=ir.get("language", "en"),
            score=score,
            ir_version="v2" if "intents" in ir else "v1",
        )

        # Add to list
        self.entries.append(entry)
        self._save()

    def get_recent(self, limit: int = 10) -> List[HistoryEntry]:
        """
        Get recent entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent entries (newest first)
        """
        return list(reversed(self.entries[-limit:]))

    def search(self, query: str, limit: int = 10) -> List[HistoryEntry]:
        """
        Search history by text

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching entries
        """
        query_lower = query.lower()
        results = [e for e in self.entries if query_lower in e.prompt_text.lower()]
        return list(reversed(results[-limit:]))

    def get_by_domain(self, domain: str, limit: int = 10) -> List[HistoryEntry]:
        """Get entries by domain"""
        results = [e for e in self.entries if e.domain == domain]
        return list(reversed(results[-limit:]))

    def get_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get entry by ID"""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def clear(self):
        """Clear all history"""
        self.entries = []
        self._save()

    def get_stats(self) -> Dict[str, Any]:
        """Get history statistics"""
        if not self.entries:
            return {
                "total": 0,
                "domains": {},
                "languages": {},
                "avg_score": 0.0,
            }

        from collections import Counter

        domains = Counter(e.domain for e in self.entries)
        languages = Counter(e.language for e in self.entries)
        scores = [e.score for e in self.entries if e.score > 0]

        return {
            "total": len(self.entries),
            "domains": dict(domains.most_common()),
            "languages": dict(languages),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "oldest": self.entries[0].timestamp if self.entries else None,
            "newest": self.entries[-1].timestamp if self.entries else None,
        }


# Global instance for convenience
_history_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """Get or create global history manager"""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager
