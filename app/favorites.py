"""
Favorites/Bookmarks Module

Allows users to bookmark their favorite prompts from history for quick access.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FavoriteEntry:
    """Single favorite/bookmark entry"""

    id: str  # Unique ID for the favorite
    prompt_id: str  # Reference to history entry hash
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    prompt_text: str = ""
    domain: str = "general"
    language: str = "en"
    score: float = 0.0
    tags: List[str] = field(default_factory=list)
    notes: str = ""  # User notes about why this is favorited
    use_count: int = 0  # How many times this favorite has been used

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FavoriteEntry":
        """Create from dictionary"""
        return cls(**data)


class FavoritesManager:
    """Manages favorite prompts storage and retrieval"""

    def __init__(self, favorites_file: Optional[Path] = None):
        """
        Initialize favorites manager

        Args:
            favorites_file: Path to favorites JSON file. Defaults to ~/.promptc/favorites.json
        """
        if favorites_file is None:
            favorites_file = Path.home() / ".promptc" / "favorites.json"

        self.favorites_file = favorites_file
        self.favorites_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing favorites
        self.entries: List[FavoriteEntry] = []
        self._load()

    def _load(self):
        """Load favorites from file"""
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [FavoriteEntry.from_dict(e) for e in data]
            except Exception:
                # If file is corrupted, start fresh
                self.entries = []

    def _save(self):
        """Save favorites to file"""
        data = [e.to_dict() for e in self.entries]
        with open(self.favorites_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(
        self,
        prompt_id: str,
        prompt_text: str,
        domain: str = "general",
        language: str = "en",
        score: float = 0.0,
        tags: Optional[List[str]] = None,
        notes: str = "",
    ) -> FavoriteEntry:
        """
        Add a prompt to favorites

        Args:
            prompt_id: ID/hash of the prompt (from history)
            prompt_text: The prompt text
            domain: Domain classification
            language: Language code
            score: Validation score
            tags: Custom tags
            notes: User notes

        Returns:
            Created FavoriteEntry
        """
        import hashlib

        # Generate unique ID for favorite
        favorite_id = hashlib.sha256(
            f"{prompt_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        # Check if already favorited
        for entry in self.entries:
            if entry.prompt_id == prompt_id:
                # Update existing favorite
                if tags:
                    entry.tags = list(set(entry.tags + tags))
                if notes:
                    entry.notes = notes
                entry.timestamp = datetime.now().isoformat()
                self._save()
                return entry

        # Create new favorite
        entry = FavoriteEntry(
            id=favorite_id,
            prompt_id=prompt_id,
            prompt_text=prompt_text[:500],  # Truncate for storage
            domain=domain,
            language=language,
            score=score,
            tags=tags or [],
            notes=notes,
        )

        self.entries.append(entry)
        self._save()
        return entry

    def remove(self, favorite_id: str) -> bool:
        """
        Remove a favorite by ID

        Args:
            favorite_id: ID of the favorite to remove

        Returns:
            True if removed, False if not found
        """
        for i, entry in enumerate(self.entries):
            if entry.id == favorite_id or entry.prompt_id == favorite_id:
                self.entries.pop(i)
                self._save()
                return True
        return False

    def get_all(self, tags: Optional[List[str]] = None, domain: Optional[str] = None) -> List[FavoriteEntry]:
        """
        Get all favorites with optional filtering

        Args:
            tags: Filter by tags (any match)
            domain: Filter by domain

        Returns:
            List of matching favorites (newest first)
        """
        results = self.entries

        if tags:
            results = [e for e in results if any(tag in e.tags for tag in tags)]

        if domain:
            results = [e for e in results if e.domain == domain]

        # Sort by timestamp, newest first
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results

    def get_by_id(self, favorite_id: str) -> Optional[FavoriteEntry]:
        """
        Get a favorite by ID

        Args:
            favorite_id: ID to search for

        Returns:
            FavoriteEntry if found, None otherwise
        """
        for entry in self.entries:
            if entry.id == favorite_id:
                return entry
        return None

    def search(self, query: str) -> List[FavoriteEntry]:
        """
        Search favorites by text

        Args:
            query: Search query

        Returns:
            Matching favorites
        """
        query_lower = query.lower()
        results = [
            e
            for e in self.entries
            if query_lower in e.prompt_text.lower()
            or query_lower in e.notes.lower()
            or any(query_lower in tag.lower() for tag in e.tags)
        ]
        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def add_tag(self, favorite_id: str, tag: str) -> bool:
        """
        Add a tag to a favorite

        Args:
            favorite_id: ID of the favorite
            tag: Tag to add

        Returns:
            True if successful, False if favorite not found
        """
        entry = self.get_by_id(favorite_id)
        if entry:
            if tag not in entry.tags:
                entry.tags.append(tag)
                self._save()
            return True
        return False

    def remove_tag(self, favorite_id: str, tag: str) -> bool:
        """
        Remove a tag from a favorite

        Args:
            favorite_id: ID of the favorite
            tag: Tag to remove

        Returns:
            True if successful, False if favorite not found
        """
        entry = self.get_by_id(favorite_id)
        if entry:
            if tag in entry.tags:
                entry.tags.remove(tag)
                self._save()
            return True
        return False

    def update_notes(self, favorite_id: str, notes: str) -> bool:
        """
        Update notes for a favorite

        Args:
            favorite_id: ID of the favorite
            notes: New notes text

        Returns:
            True if successful, False if favorite not found
        """
        entry = self.get_by_id(favorite_id)
        if entry:
            entry.notes = notes
            self._save()
            return True
        return False

    def increment_use_count(self, favorite_id: str) -> bool:
        """
        Increment use count for a favorite

        Args:
            favorite_id: ID of the favorite

        Returns:
            True if successful, False if favorite not found
        """
        entry = self.get_by_id(favorite_id)
        if entry:
            entry.use_count += 1
            self._save()
            return True
        return False

    def get_most_used(self, limit: int = 10) -> List[FavoriteEntry]:
        """
        Get most frequently used favorites

        Args:
            limit: Maximum number of favorites to return

        Returns:
            List of favorites sorted by use count
        """
        sorted_entries = sorted(self.entries, key=lambda x: x.use_count, reverse=True)
        return sorted_entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get favorites statistics"""
        if not self.entries:
            return {
                "total": 0,
                "domains": {},
                "tags": {},
                "languages": {},
                "avg_score": 0.0,
            }

        from collections import Counter

        domains = Counter(e.domain for e in self.entries)
        languages = Counter(e.language for e in self.entries)

        # Flatten all tags
        all_tags = [tag for e in self.entries for tag in e.tags]
        tags = Counter(all_tags)

        scores = [e.score for e in self.entries if e.score > 0]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        total_uses = sum(e.use_count for e in self.entries)

        return {
            "total": len(self.entries),
            "domains": dict(domains.most_common()),
            "tags": dict(tags.most_common()),
            "languages": dict(languages),
            "avg_score": round(avg_score, 2),
            "total_uses": total_uses,
        }

    def clear(self):
        """Clear all favorites"""
        self.entries = []
        self._save()


def get_favorites_manager() -> FavoritesManager:
    """Get or create favorites manager instance"""
    return FavoritesManager()
