"""
Smart Search - Unified search across all PromptC data sources.

Search across history, favorites, templates, snippets, and collections
with relevance scoring and result ranking.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class SearchResultType(str, Enum):
    """Types of search results."""

    HISTORY = "history"
    FAVORITE = "favorite"
    TEMPLATE = "template"
    SNIPPET = "snippet"
    COLLECTION = "collection"


@dataclass
class SearchResult:
    """A single search result."""

    result_type: SearchResultType
    id: str
    title: str
    content: str
    score: float  # Relevance score 0-100
    metadata: Dict[str, Any]  # Additional info (tags, domain, etc.)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.result_type.value,
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "score": round(self.score, 2),
            "metadata": self.metadata,
        }


class SmartSearch:
    """Unified search engine for all PromptC data."""

    def __init__(self):
        """Initialize the search engine."""
        # Import managers lazily to avoid circular imports
        from app.history import get_history_manager
        from app.favorites import get_favorites_manager
        from app.templates_manager import get_templates_manager
        from app.snippets import get_snippets_manager
        from app.collections import get_collections_manager

        self.history_mgr = get_history_manager()
        self.favorites_mgr = get_favorites_manager()
        self.templates_mgr = get_templates_manager()
        self.snippets_mgr = get_snippets_manager()
        self.collections_mgr = get_collections_manager()

    def search(
        self,
        query: str,
        result_types: Optional[List[SearchResultType]] = None,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """Search across all data sources.

        Args:
            query: Search query string
            result_types: Filter by result types (None = all)
            limit: Maximum number of results
            min_score: Minimum relevance score (0-100)

        Returns:
            List of SearchResult objects, sorted by score
        """
        if not query or not query.strip():
            return []

        query_lower = query.lower().strip()
        results: List[SearchResult] = []

        # Determine which sources to search
        types_to_search = result_types or list(SearchResultType)

        # Search history
        if SearchResultType.HISTORY in types_to_search:
            results.extend(self._search_history(query_lower))

        # Search favorites
        if SearchResultType.FAVORITE in types_to_search:
            results.extend(self._search_favorites(query_lower))

        # Search templates
        if SearchResultType.TEMPLATE in types_to_search:
            results.extend(self._search_templates(query_lower))

        # Search snippets
        if SearchResultType.SNIPPET in types_to_search:
            results.extend(self._search_snippets(query_lower))

        # Search collections
        if SearchResultType.COLLECTION in types_to_search:
            results.extend(self._search_collections(query_lower))

        # Filter by minimum score
        results = [r for r in results if r.score >= min_score]

        # Sort by score (highest first)
        results.sort(key=lambda r: r.score, reverse=True)

        # Limit results
        return results[:limit]

    def _search_history(self, query: str) -> List[SearchResult]:
        """Search history entries."""
        results = []

        try:
            entries = self.history_mgr.get_recent(limit=100)

            for entry in entries:
                score = self._calculate_score(
                    query,
                    [
                        entry.prompt_text,
                        entry.domain or "",
                        entry.language or "",
                    ],
                )

                if score > 0:
                    results.append(
                        SearchResult(
                            result_type=SearchResultType.HISTORY,
                            id=entry.id,
                            title=self._truncate(entry.prompt_text, 60),
                            content=entry.prompt_text,
                            score=score,
                            metadata={
                                "domain": entry.domain,
                                "language": entry.language,
                                "score": entry.score,
                                "timestamp": entry.timestamp,
                            },
                        )
                    )
        except Exception:
            pass  # Gracefully handle if history is empty

        return results

    def _search_favorites(self, query: str) -> List[SearchResult]:
        """Search favorite entries."""
        results = []

        try:
            favorites = self.favorites_mgr.get_all()

            for fav in favorites:
                score = self._calculate_score(
                    query,
                    [
                        fav.prompt_text,
                        fav.notes or "",
                        fav.domain or "",
                        " ".join(fav.tags),
                    ],
                )

                if score > 0:
                    results.append(
                        SearchResult(
                            result_type=SearchResultType.FAVORITE,
                            id=fav.id,
                            title=self._truncate(fav.prompt_text, 60),
                            content=fav.prompt_text,
                            score=score * 1.1,  # Boost favorites slightly
                            metadata={
                                "tags": fav.tags,
                                "domain": fav.domain,
                                "notes": fav.notes,
                                "use_count": fav.use_count,
                                "score": fav.score,
                            },
                        )
                    )
        except Exception:
            pass

        return results

    def _search_templates(self, query: str) -> List[SearchResult]:
        """Search templates."""
        results = []

        try:
            templates = self.templates_mgr.list_templates()

            for template in templates:
                score = self._calculate_score(
                    query,
                    [
                        template.id,
                        template.description,
                        template.category or "",
                        " ".join(template.tags),
                        template.content,
                    ],
                )

                if score > 0:
                    results.append(
                        SearchResult(
                            result_type=SearchResultType.TEMPLATE,
                            id=template.id,
                            title=template.id.replace("_", " ").title(),
                            content=template.description,
                            score=score,
                            metadata={
                                "category": template.category,
                                "tags": template.tags,
                                "variables": list(template.variables.keys()),
                            },
                        )
                    )
        except Exception:
            pass

        return results

    def _search_snippets(self, query: str) -> List[SearchResult]:
        """Search snippets."""
        results = []

        try:
            snippets = self.snippets_mgr.get_all()

            for snippet in snippets:
                score = self._calculate_score(
                    query,
                    [
                        snippet.title,
                        snippet.content,
                        snippet.description or "",
                        snippet.category or "",
                        " ".join(snippet.tags),
                    ],
                )

                if score > 0:
                    results.append(
                        SearchResult(
                            result_type=SearchResultType.SNIPPET,
                            id=snippet.id,
                            title=snippet.title,
                            content=snippet.content,
                            score=score,
                            metadata={
                                "category": snippet.category,
                                "tags": snippet.tags,
                                "use_count": snippet.use_count,
                                "language": snippet.language,
                            },
                        )
                    )
        except Exception:
            pass

        return results

    def _search_collections(self, query: str) -> List[SearchResult]:
        """Search collections."""
        results = []

        try:
            collections = self.collections_mgr.get_all()

            for collection in collections:
                score = self._calculate_score(
                    query,
                    [
                        collection.name,
                        collection.description,
                        collection.id,
                        " ".join(collection.tags),
                    ],
                )

                if score > 0:
                    total_items = (
                        len(collection.prompts)
                        + len(collection.templates)
                        + len(collection.snippets)
                    )

                    results.append(
                        SearchResult(
                            result_type=SearchResultType.COLLECTION,
                            id=collection.id,
                            title=collection.name,
                            content=collection.description,
                            score=score,
                            metadata={
                                "tags": collection.tags,
                                "items": total_items,
                                "use_count": collection.use_count,
                                "archived": collection.is_archived,
                            },
                        )
                    )
        except Exception:
            pass

        return results

    def _calculate_score(self, query: str, fields: List[str]) -> float:
        """Calculate relevance score for a query against multiple fields.

        Args:
            query: Search query
            fields: List of text fields to search in

        Returns:
            Relevance score (0-100)
        """
        if not query:
            return 0.0

        query_words = query.lower().split()
        total_score = 0.0
        max_possible = 0.0

        for field in fields:
            if not field:
                continue

            field_lower = field.lower()
            field_score = 0.0

            # Exact match (highest score)
            if query in field_lower:
                field_score = 100.0
            # All words present
            elif all(word in field_lower for word in query_words):
                field_score = 80.0
            # Partial word matches
            else:
                matches = sum(1 for word in query_words if word in field_lower)
                if matches > 0:
                    field_score = (matches / len(query_words)) * 60.0

            total_score += field_score
            max_possible += 100.0

        # Normalize to 0-100
        if max_possible > 0:
            return (total_score / max_possible) * 100
        return 0.0

    def _truncate(self, text: str, length: int) -> str:
        """Truncate text to specified length."""
        if len(text) <= length:
            return text
        return text[: length - 3] + "..."

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about searchable items.

        Returns:
            Dictionary with counts per type
        """
        try:
            return {
                "history": len(self.history_mgr.get_recent(limit=1000)),
                "favorites": len(self.favorites_mgr.get_all()),
                "templates": len(self.templates_mgr.list_templates()),
                "snippets": len(self.snippets_mgr.get_all()),
                "collections": len(self.collections_mgr.get_all()),
            }
        except Exception:
            return {
                "history": 0,
                "favorites": 0,
                "templates": 0,
                "snippets": 0,
                "collections": 0,
            }


# Singleton instance
_search_engine: Optional[SmartSearch] = None


def get_search_engine() -> SmartSearch:
    """Get the global search engine instance.

    Returns:
        The SmartSearch singleton
    """
    global _search_engine
    if _search_engine is None:
        _search_engine = SmartSearch()
    return _search_engine
