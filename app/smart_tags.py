"""Smart tags and auto-categorization system."""

from collections import Counter
from typing import Dict, List, Set, Tuple, Optional
import re

from app.history import get_history_manager
from app.favorites import get_favorites_manager
from app.templates_manager import get_templates_manager
from app.snippets import get_snippets_manager
from app.collections import get_collections_manager


# Domain to tags mapping
DOMAIN_TAG_MAP = {
    "tech": ["coding", "development", "software", "programming"],
    "education": ["learning", "teaching", "tutorial", "academic"],
    "business": ["corporate", "professional", "enterprise", "management"],
    "creative": ["design", "art", "creative", "media"],
    "science": ["research", "academic", "analysis", "data"],
    "health": ["medical", "wellness", "healthcare", "fitness"],
    "finance": ["financial", "money", "investment", "trading"],
    "marketing": ["advertising", "promotion", "social-media", "branding"],
    "writing": ["content", "documentation", "copywriting", "editorial"],
    "productivity": ["efficiency", "automation", "workflow", "tools"],
}

# Keyword patterns for tag suggestions
KEYWORD_PATTERNS = {
    "python": ["python", "py", "django", "flask", "pandas"],
    "javascript": ["javascript", "js", "node", "react", "vue", "angular"],
    "web": ["web", "html", "css", "frontend", "backend", "api"],
    "database": ["database", "sql", "nosql", "mongodb", "postgresql"],
    "cloud": ["cloud", "aws", "azure", "gcp", "kubernetes", "docker"],
    "ai": ["ai", "ml", "machine-learning", "deep-learning", "neural"],
    "security": ["security", "encryption", "authentication", "vulnerability"],
    "testing": ["test", "testing", "qa", "automation", "unit-test"],
    "debug": ["debug", "debugging", "troubleshoot", "error", "bug"],
    "documentation": ["doc", "documentation", "readme", "guide", "manual"],
}


class SmartTagger:
    """Smart tagging engine for automatic tag suggestions and management."""

    def __init__(self):
        """Initialize SmartTagger with all managers."""
        self.history_mgr = get_history_manager()
        self.favorites_mgr = get_favorites_manager()
        self.templates_mgr = get_templates_manager()
        self.snippets_mgr = get_snippets_manager()
        self.collections_mgr = get_collections_manager()

    def suggest_tags_for_text(self, text: str, domain: Optional[str] = None) -> List[str]:
        """Suggest tags based on text content and optional domain.

        Args:
            text: Text content to analyze
            domain: Optional domain hint

        Returns:
            List of suggested tags
        """
        suggested = set()

        # Add domain-based tags
        if domain and domain in DOMAIN_TAG_MAP:
            suggested.update(DOMAIN_TAG_MAP[domain])

        # Analyze text for keyword patterns
        text_lower = text.lower()
        for tag, keywords in KEYWORD_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                suggested.add(tag)

        # Extract potential tags from text (hashtags or quoted terms)
        hashtags = re.findall(r"#(\w+)", text)
        suggested.update(hashtags)

        return sorted(list(suggested))

    def suggest_tags_for_prompt(self, prompt_id: str) -> List[str]:
        """Suggest tags for a specific prompt in history.

        Args:
            prompt_id: Prompt ID

        Returns:
            List of suggested tags
        """
        # Try to find in history
        history = self.history_mgr.get_recent(limit=10000)
        prompt = next((h for h in history if h.id == prompt_id), None)

        if not prompt:
            return []

        # Combine prompt text and domain
        text = f"{prompt.prompt_text} {prompt.role or ''}"
        return self.suggest_tags_for_text(text, prompt.domain)

    def suggest_tags_for_favorite(self, favorite_id: str) -> List[str]:
        """Suggest tags for a favorite.

        Args:
            favorite_id: Favorite ID

        Returns:
            List of suggested tags
        """
        # Find favorite by ID
        favorites = self.favorites_mgr.get_all()
        favorite = next((f for f in favorites if f.id == favorite_id), None)

        if not favorite:
            return []

        # Analyze favorite content
        text = f"{favorite.prompt_text} {favorite.notes or ''}"
        return self.suggest_tags_for_text(text, favorite.domain)

    def auto_tag_all_prompts(self, dry_run: bool = False) -> Dict[str, List[str]]:
        """Auto-tag all prompts in history.

        Args:
            dry_run: If True, only return suggestions without applying

        Returns:
            Dict mapping prompt_id to suggested tags
        """
        suggestions = {}
        history = self.history_mgr.get_recent(limit=10000)

        for prompt in history:
            # Get current tags
            current_tags = set(getattr(prompt, "tags", []) or [])

            # Get suggestions
            suggested = set(self.suggest_tags_for_text(prompt.prompt_text, prompt.domain))

            # Only suggest new tags
            new_tags = suggested - current_tags
            if new_tags:
                suggestions[prompt.id] = sorted(list(new_tags))

                # Apply if not dry run
                if not dry_run and hasattr(prompt, "tags"):
                    prompt.tags = sorted(list(current_tags | new_tags))

        if not dry_run:
            self.history_mgr.save()

        return suggestions

    def auto_tag_all_favorites(self, dry_run: bool = False) -> Dict[str, List[str]]:
        """Auto-tag all favorites.

        Args:
            dry_run: If True, only return suggestions without applying

        Returns:
            Dict mapping favorite_id to suggested tags
        """
        suggestions = {}
        favorites = self.favorites_mgr.get_all()

        for favorite in favorites:
            current_tags = set(favorite.tags)
            text = f"{favorite.prompt_text} {favorite.notes or ''}"
            suggested = set(self.suggest_tags_for_text(text, favorite.domain))

            new_tags = suggested - current_tags
            if new_tags:
                suggestions[favorite.id] = sorted(list(new_tags))

                if not dry_run:
                    favorite.tags = sorted(list(current_tags | new_tags))

        if not dry_run:
            self.favorites_mgr.save()

        return suggestions

    def get_all_tags(self) -> Set[str]:
        """Get all unique tags across all data sources.

        Returns:
            Set of all unique tags
        """
        all_tags = set()

        # From history
        for prompt in self.history_mgr.get_recent(limit=10000):
            if hasattr(prompt, "tags") and prompt.tags:
                all_tags.update(prompt.tags)

        # From favorites
        for fav in self.favorites_mgr.get_all():
            all_tags.update(fav.tags)

        # From templates
        for template in self.templates_mgr.list_templates():
            all_tags.update(template.tags)

        # From snippets
        for snippet in self.snippets_mgr.get_all():
            all_tags.update(snippet.tags)

        # From collections
        for collection in self.collections_mgr.get_all():
            all_tags.update(collection.tags)

        return all_tags

    def get_tag_statistics(self) -> List[Tuple[str, int]]:
        """Get usage statistics for all tags.

        Returns:
            List of (tag, count) tuples sorted by count
        """
        tag_counter = Counter()

        # Count in history
        for prompt in self.history_mgr.get_recent(limit=10000):
            if hasattr(prompt, "tags") and prompt.tags:
                tag_counter.update(prompt.tags)

        # Count in favorites
        for fav in self.favorites_mgr.get_all():
            tag_counter.update(fav.tags)

        # Count in templates
        for template in self.templates_mgr.list_templates():
            tag_counter.update(template.tags)

        # Count in snippets
        for snippet in self.snippets_mgr.get_all():
            tag_counter.update(snippet.tags)

        # Count in collections
        for collection in self.collections_mgr.get_all():
            tag_counter.update(collection.tags)

        return tag_counter.most_common()

    def find_unused_tags(self) -> Set[str]:
        """Find tags that are defined but never used.

        Returns:
            Set of unused tags
        """
        # Get all potential tags from patterns
        potential_tags = set(KEYWORD_PATTERNS.keys())
        for tags in DOMAIN_TAG_MAP.values():
            potential_tags.update(tags)

        # Get actually used tags
        used_tags = self.get_all_tags()

        # Return difference
        return potential_tags - used_tags

    def get_tag_cooccurrence(self, tag: str, limit: int = 5) -> List[Tuple[str, int]]:
        """Find tags that commonly appear together with given tag.

        Args:
            tag: Tag to analyze
            limit: Maximum number of co-occurring tags to return

        Returns:
            List of (co-occurring_tag, count) tuples
        """
        cooccurrence = Counter()

        # Check all sources
        all_items = []

        # History
        for prompt in self.history_mgr.get_recent(limit=10000):
            if hasattr(prompt, "tags") and prompt.tags:
                all_items.append(prompt.tags)

        # Favorites
        for fav in self.favorites_mgr.get_all():
            all_items.append(fav.tags)

        # Templates
        for template in self.templates_mgr.list_templates():
            all_items.append(template.tags)

        # Snippets
        for snippet in self.snippets_mgr.get_all():
            all_items.append(snippet.tags)

        # Collections
        for collection in self.collections_mgr.get_all():
            all_items.append(collection.tags)

        # Count co-occurrences
        for tags in all_items:
            if tag in tags:
                for other_tag in tags:
                    if other_tag != tag:
                        cooccurrence[other_tag] += 1

        return cooccurrence.most_common(limit)

    def normalize_tags(self, dry_run: bool = False) -> Dict[str, str]:
        """Normalize tag names (lowercase, remove duplicates).

        Args:
            dry_run: If True, only return changes without applying

        Returns:
            Dict mapping old tag to normalized tag
        """
        changes = {}
        all_tags = self.get_all_tags()

        # Build normalization map
        normalized_map = {}
        for tag in all_tags:
            normalized = tag.lower().strip().replace(" ", "-")
            if normalized != tag:
                normalized_map[tag] = normalized
                changes[tag] = normalized

        if not dry_run and normalized_map:
            # Apply to all sources
            # History
            for prompt in self.history_mgr.get_recent(limit=10000):
                if hasattr(prompt, "tags") and prompt.tags:
                    prompt.tags = [normalized_map.get(t, t) for t in prompt.tags]
            self.history_mgr.save()

            # Favorites
            for fav in self.favorites_mgr.get_all():
                fav.tags = [normalized_map.get(t, t) for t in fav.tags]
            self.favorites_mgr.save()

            # Templates would need update methods
            # Snippets would need update methods
            # Collections would need update methods

        return changes

    def suggest_similar_items_tags(self, item_id: str, source: str = "favorites") -> List[str]:
        """Suggest tags based on similar items.

        Args:
            item_id: Item ID
            source: Source type (favorites, templates, snippets)

        Returns:
            List of suggested tags from similar items
        """
        # This would use similarity search to find related items
        # and aggregate their tags
        suggested_tags = set()

        if source == "favorites":
            # Find favorite by ID
            favorites = self.favorites_mgr.get_all()
            favorite = next((f for f in favorites if f.id == item_id), None)

            if not favorite:
                return []

            # Simple similarity: same domain
            similar = [
                f
                for f in self.favorites_mgr.get_all()
                if f.id != item_id and f.domain == favorite.domain
            ]

            for item in similar[:5]:  # Top 5 similar
                suggested_tags.update(item.tags)

            # Remove tags already on this item
            suggested_tags -= set(favorite.tags)

        return sorted(list(suggested_tags))


# Singleton instance
_smart_tagger_instance = None


def get_smart_tagger() -> SmartTagger:
    """Get the singleton SmartTagger instance.

    Returns:
        SmartTagger instance
    """
    global _smart_tagger_instance
    if _smart_tagger_instance is None:
        _smart_tagger_instance = SmartTagger()
    return _smart_tagger_instance
