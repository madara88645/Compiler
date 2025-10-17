"""Quick action utilities for common operations."""

import random
from typing import Optional, List
from pathlib import Path

from app.search_history import get_search_history_manager
from app.favorites import get_favorites_manager
from app.templates_manager import get_templates_manager
from app.snippets import get_snippets_manager


class QuickActions:
    """Provides quick action utilities."""

    def __init__(self):
        """Initialize quick actions."""
        self.search_history = get_search_history_manager()
        self.favorites_mgr = get_favorites_manager()
        self.templates_mgr = get_templates_manager()
        self.snippets_mgr = get_snippets_manager()

    def get_last_search(self) -> Optional[dict]:
        """Get the last search query and details.

        Returns:
            Dictionary with query, result_count, timestamp, etc. or None if no history
        """
        recent = self.search_history.get_recent(limit=1)
        if not recent:
            return None

        entry = recent[0]
        return {
            "query": entry.query,
            "result_count": entry.result_count,
            "timestamp": entry.timestamp,
            "types_filter": entry.types_filter,
            "min_score": entry.min_score,
        }

    def get_top_favorites(self, limit: int = 10) -> List[dict]:
        """Get top favorites sorted by score.

        Args:
            limit: Maximum number of favorites to return

        Returns:
            List of favorite dictionaries sorted by score (highest first)
        """
        favorites = self.favorites_mgr.get_all()
        if not favorites:
            return []

        # Sort by score descending
        sorted_favs = sorted(favorites, key=lambda x: x.score or 0, reverse=True)

        # Convert to dict format
        results = []
        for fav in sorted_favs[:limit]:
            results.append(
                {
                    "id": fav.id,
                    "prompt_text": fav.prompt_text,
                    "score": fav.score,
                    "domain": fav.domain,
                    "tags": fav.tags,
                    "notes": fav.notes,
                    "use_count": fav.use_count,
                    "timestamp": fav.timestamp,
                }
            )

        return results

    def get_random_template(self) -> Optional[dict]:
        """Get a random template.

        Returns:
            Template dictionary or None if no templates exist
        """
        templates = self.templates_mgr.list_templates()
        if not templates:
            return None

        template = random.choice(templates)
        return {
            "name": template.name,
            "description": template.description,
            "template_text": template.template_text,
            "variables": [v.name for v in template.variables] if template.variables else [],
            "category": template.category,
            "tags": template.tags,
        }

    def get_random_snippet(self) -> Optional[dict]:
        """Get a random snippet.

        Returns:
            Snippet dictionary or None if no snippets exist
        """
        snippets = self.snippets_mgr.get_all()
        if not snippets:
            return None

        snippet = random.choice(snippets)
        return {
            "title": snippet.title,
            "content": snippet.content,
            "category": snippet.category,
            "description": snippet.description,
            "tags": snippet.tags,
            "use_count": snippet.use_count,
        }

    def get_random_item(self, item_type: Optional[str] = None) -> Optional[dict]:
        """Get a random item of specified type or any type.

        Args:
            item_type: 'template', 'snippet', or None for random type

        Returns:
            Item dictionary with 'type' and 'data' keys, or None if no items
        """
        if item_type == "template":
            data = self.get_random_template()
            return {"type": "template", "data": data} if data else None

        elif item_type == "snippet":
            data = self.get_random_snippet()
            return {"type": "snippet", "data": data} if data else None

        else:
            # Random type selection
            available_types = []
            if self.templates_mgr.list_templates():
                available_types.append("template")
            if self.snippets_mgr.get_all():
                available_types.append("snippet")

            if not available_types:
                return None

            selected_type = random.choice(available_types)
            return self.get_random_item(item_type=selected_type)


# Singleton instance
_quick_actions_instance = None


def get_quick_actions() -> QuickActions:
    """Get the singleton QuickActions instance.

    Returns:
        QuickActions instance
    """
    global _quick_actions_instance
    if _quick_actions_instance is None:
        _quick_actions_instance = QuickActions()
    return _quick_actions_instance
