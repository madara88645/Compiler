"""Quick snippets management for reusable prompt fragments.

Snippets are small, reusable pieces of text that can be quickly inserted
into prompts. Unlike templates (which are full prompts with variables),
snippets are fragments like constraints, examples, or context pieces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Snippet:
    """A reusable prompt fragment."""

    id: str
    title: str
    content: str
    category: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    use_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None
    language: str = "en"  # Language of the snippet content

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "description": self.description,
            "tags": self.tags,
            "use_count": self.use_count,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Snippet:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            category=data["category"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
            use_count=data.get("use_count", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_used=data.get("last_used"),
            language=data.get("language", "en"),
        )


class SnippetsManager:
    """Manage quick snippets for reusable prompt fragments."""

    def __init__(self, snippets_file: Optional[Path] = None):
        self.snippets_file = snippets_file or (Path.home() / ".promptc" / "snippets.json")
        self.snippets_file.parent.mkdir(parents=True, exist_ok=True)
        self._snippets: Dict[str, Snippet] = {}
        self._load_snippets()

    def _load_snippets(self) -> None:
        """Load snippets from disk."""
        if not self.snippets_file.exists():
            self._snippets = {}
            return

        try:
            with open(self.snippets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._snippets = {
                    sid: Snippet.from_dict(snippet_data) for sid, snippet_data in data.items()
                }
        except Exception:
            self._snippets = {}

    def _save_snippets(self) -> None:
        """Save snippets to disk."""
        data = {sid: snippet.to_dict() for sid, snippet in self._snippets.items()}

        with open(self.snippets_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(
        self,
        snippet_id: str,
        title: str,
        content: str,
        category: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        language: str = "en",
    ) -> Snippet:
        """
        Add a new snippet.

        Args:
            snippet_id: Unique identifier
            title: Short title
            content: Snippet content/text
            category: Category (constraint, example, context, etc.)
            description: Optional description
            tags: Optional tags
            language: Content language

        Returns:
            Created snippet

        Raises:
            ValueError: If snippet_id already exists
        """
        if snippet_id in self._snippets:
            raise ValueError(f"Snippet '{snippet_id}' already exists")

        snippet = Snippet(
            id=snippet_id,
            title=title,
            content=content,
            category=category,
            description=description,
            tags=tags or [],
            language=language,
        )

        self._snippets[snippet_id] = snippet
        self._save_snippets()

        return snippet

    def get(self, snippet_id: str) -> Optional[Snippet]:
        """Get a snippet by ID."""
        return self._snippets.get(snippet_id)

    def get_all(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: Optional[str] = None,
    ) -> List[Snippet]:
        """
        Get all snippets with optional filtering.

        Args:
            category: Filter by category
            tags: Filter by tags (snippet must have all tags)
            language: Filter by language

        Returns:
            List of matching snippets
        """
        snippets = list(self._snippets.values())

        if category:
            snippets = [s for s in snippets if s.category == category]

        if tags:
            snippets = [s for s in snippets if all(tag in s.tags for tag in tags)]

        if language:
            snippets = [s for s in snippets if s.language == language]

        # Sort by use count (most used first), then by title
        return sorted(snippets, key=lambda s: (-s.use_count, s.title))

    def search(self, query: str) -> List[Snippet]:
        """
        Search snippets by query string.

        Searches in title, description, content, and tags.

        Args:
            query: Search query

        Returns:
            List of matching snippets
        """
        query_lower = query.lower()
        results = []

        for snippet in self._snippets.values():
            if (
                query_lower in snippet.title.lower()
                or query_lower in snippet.description.lower()
                or query_lower in snippet.content.lower()
                or any(query_lower in tag.lower() for tag in snippet.tags)
            ):
                results.append(snippet)

        # Sort by use count
        return sorted(results, key=lambda s: -s.use_count)

    def update(
        self,
        snippet_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Snippet]:
        """
        Update a snippet.

        Args:
            snippet_id: Snippet to update
            title: New title (optional)
            content: New content (optional)
            description: New description (optional)
            category: New category (optional)
            tags: New tags (optional)

        Returns:
            Updated snippet or None if not found
        """
        snippet = self._snippets.get(snippet_id)
        if not snippet:
            return None

        if title is not None:
            snippet.title = title
        if content is not None:
            snippet.content = content
        if description is not None:
            snippet.description = description
        if category is not None:
            snippet.category = category
        if tags is not None:
            snippet.tags = tags

        self._save_snippets()
        return snippet

    def delete(self, snippet_id: str) -> bool:
        """
        Delete a snippet.

        Args:
            snippet_id: Snippet to delete

        Returns:
            True if deleted successfully
        """
        if snippet_id in self._snippets:
            del self._snippets[snippet_id]
            self._save_snippets()
            return True
        return False

    def use(self, snippet_id: str) -> Optional[str]:
        """
        Use a snippet (increment use count and return content).

        Args:
            snippet_id: Snippet to use

        Returns:
            Snippet content or None if not found
        """
        snippet = self._snippets.get(snippet_id)
        if not snippet:
            return None

        snippet.use_count += 1
        snippet.last_used = datetime.now().isoformat()
        self._save_snippets()

        return snippet.content

    def add_tag(self, snippet_id: str, tag: str) -> bool:
        """Add a tag to a snippet."""
        snippet = self._snippets.get(snippet_id)
        if not snippet:
            return False

        if tag not in snippet.tags:
            snippet.tags.append(tag)
            self._save_snippets()

        return True

    def remove_tag(self, snippet_id: str, tag: str) -> bool:
        """Remove a tag from a snippet."""
        snippet = self._snippets.get(snippet_id)
        if not snippet:
            return False

        if tag in snippet.tags:
            snippet.tags.remove(tag)
            self._save_snippets()

        return True

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        categories = {s.category for s in self._snippets.values()}
        return sorted(categories)

    def get_most_used(self, limit: int = 10) -> List[Snippet]:
        """Get most used snippets."""
        snippets = sorted(self._snippets.values(), key=lambda s: -s.use_count)
        return snippets[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about snippets."""
        if not self._snippets:
            return {
                "total_snippets": 0,
                "total_uses": 0,
                "categories": {},
                "languages": {},
                "most_used": [],
            }

        categories: Dict[str, int] = {}
        languages: Dict[str, int] = {}
        total_uses = 0

        for snippet in self._snippets.values():
            categories[snippet.category] = categories.get(snippet.category, 0) + 1
            languages[snippet.language] = languages.get(snippet.language, 0) + 1
            total_uses += snippet.use_count

        most_used = self.get_most_used(5)

        return {
            "total_snippets": len(self._snippets),
            "total_uses": total_uses,
            "categories": categories,
            "languages": languages,
            "most_used": [
                {
                    "id": s.id,
                    "title": s.title,
                    "category": s.category,
                    "use_count": s.use_count,
                }
                for s in most_used
            ],
        }

    def clear(self) -> None:
        """Clear all snippets."""
        self._snippets = {}
        self._save_snippets()


# Global manager instance
_manager: Optional[SnippetsManager] = None


def get_snippets_manager() -> SnippetsManager:
    """Get the global snippets manager instance."""
    global _manager
    if _manager is None:
        _manager = SnippetsManager()
    return _manager


__all__ = ["Snippet", "SnippetsManager", "get_snippets_manager"]
