"""
Collections/Workspaces management for organizing prompts, templates, and snippets.

A collection is a workspace that groups related prompts, templates, and snippets
together for project-based organization.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class Collection:
    """A collection/workspace for organizing related prompt assets."""

    id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Associated items
    prompts: List[str] = field(default_factory=list)  # List of prompt IDs/hashes
    templates: List[str] = field(default_factory=list)  # List of template IDs
    snippets: List[str] = field(default_factory=list)  # List of snippet IDs

    # Metadata
    tags: List[str] = field(default_factory=list)
    color: str = "blue"  # For UI display
    is_archived: bool = False
    use_count: int = 0
    last_used: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Collection":
        """Create from dictionary."""
        return cls(**data)

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()

    def increment_use(self) -> None:
        """Increment use count and update last_used."""
        self.use_count += 1
        self.last_used = datetime.now().isoformat()
        self.update_timestamp()


class CollectionsManager:
    """Manager for collections/workspaces."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the collections manager.

        Args:
            storage_path: Path to the collections JSON file.
                         Defaults to ~/.promptc/collections.json
        """
        if storage_path is None:
            storage_path = Path.home() / ".promptc" / "collections.json"
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Active collection tracking
        self.active_collection_path = Path.home() / ".promptc" / "active_collection.txt"

        self.collections: Dict[str, Collection] = self._load_collections()

    def _load_collections(self) -> Dict[str, Collection]:
        """Load collections from storage."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {cid: Collection.from_dict(cdata) for cid, cdata in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_collections(self) -> None:
        """Save collections to storage."""
        data = {cid: col.to_dict() for cid, col in self.collections.items()}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create(
        self,
        collection_id: str,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        color: str = "blue",
    ) -> Collection:
        """Create a new collection.

        Args:
            collection_id: Unique identifier for the collection
            name: Display name
            description: Optional description
            tags: Optional tags for categorization
            color: Color for UI display (default: blue)

        Returns:
            The created collection

        Raises:
            ValueError: If collection_id already exists
        """
        if collection_id in self.collections:
            raise ValueError(f"Collection '{collection_id}' already exists")

        collection = Collection(
            id=collection_id,
            name=name,
            description=description,
            tags=tags or [],
            color=color,
        )
        self.collections[collection_id] = collection
        self._save_collections()
        return collection

    def get(self, collection_id: str) -> Optional[Collection]:
        """Get a collection by ID.

        Args:
            collection_id: The collection ID

        Returns:
            The collection or None if not found
        """
        return self.collections.get(collection_id)

    def get_all(
        self,
        tag: Optional[str] = None,
        archived: Optional[bool] = None,
    ) -> List[Collection]:
        """Get all collections with optional filtering.

        Args:
            tag: Filter by tag
            archived: Filter by archived status (None = all)

        Returns:
            List of collections
        """
        collections = list(self.collections.values())

        if tag:
            collections = [c for c in collections if tag in c.tags]

        if archived is not None:
            collections = [c for c in collections if c.is_archived == archived]

        return sorted(collections, key=lambda c: c.updated_at, reverse=True)

    def update(
        self,
        collection_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        color: Optional[str] = None,
    ) -> Collection:
        """Update a collection.

        Args:
            collection_id: The collection ID
            name: New name (optional)
            description: New description (optional)
            tags: New tags (optional)
            color: New color (optional)

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if name is not None:
            collection.name = name
        if description is not None:
            collection.description = description
        if tags is not None:
            collection.tags = tags
        if color is not None:
            collection.color = color

        collection.update_timestamp()
        self._save_collections()
        return collection

    def delete(self, collection_id: str) -> bool:
        """Delete a collection.

        Args:
            collection_id: The collection ID

        Returns:
            True if deleted, False if not found
        """
        if collection_id in self.collections:
            del self.collections[collection_id]
            self._save_collections()

            # Clear active collection if it was deleted
            if self.get_active_collection() == collection_id:
                self.set_active_collection(None)

            return True
        return False

    def archive(self, collection_id: str) -> Collection:
        """Archive a collection.

        Args:
            collection_id: The collection ID

        Returns:
            The archived collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        collection.is_archived = True
        collection.update_timestamp()
        self._save_collections()
        return collection

    def unarchive(self, collection_id: str) -> Collection:
        """Unarchive a collection.

        Args:
            collection_id: The collection ID

        Returns:
            The unarchived collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        collection.is_archived = False
        collection.update_timestamp()
        self._save_collections()
        return collection

    # Item management methods

    def add_prompt(self, collection_id: str, prompt_id: str) -> Collection:
        """Add a prompt to a collection.

        Args:
            collection_id: The collection ID
            prompt_id: The prompt ID/hash to add

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if prompt_id not in collection.prompts:
            collection.prompts.append(prompt_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    def add_template(self, collection_id: str, template_id: str) -> Collection:
        """Add a template to a collection.

        Args:
            collection_id: The collection ID
            template_id: The template ID to add

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if template_id not in collection.templates:
            collection.templates.append(template_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    def add_snippet(self, collection_id: str, snippet_id: str) -> Collection:
        """Add a snippet to a collection.

        Args:
            collection_id: The collection ID
            snippet_id: The snippet ID to add

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if snippet_id not in collection.snippets:
            collection.snippets.append(snippet_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    def remove_prompt(self, collection_id: str, prompt_id: str) -> Collection:
        """Remove a prompt from a collection.

        Args:
            collection_id: The collection ID
            prompt_id: The prompt ID to remove

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if prompt_id in collection.prompts:
            collection.prompts.remove(prompt_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    def remove_template(self, collection_id: str, template_id: str) -> Collection:
        """Remove a template from a collection.

        Args:
            collection_id: The collection ID
            template_id: The template ID to remove

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if template_id in collection.templates:
            collection.templates.remove(template_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    def remove_snippet(self, collection_id: str, snippet_id: str) -> Collection:
        """Remove a snippet from a collection.

        Args:
            collection_id: The collection ID
            snippet_id: The snippet ID to remove

        Returns:
            The updated collection

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        if snippet_id in collection.snippets:
            collection.snippets.remove(snippet_id)
            collection.update_timestamp()
            self._save_collections()

        return collection

    # Active collection management

    def set_active_collection(self, collection_id: Optional[str]) -> Optional[str]:
        """Set the active collection.

        Args:
            collection_id: The collection ID to set as active, or None to clear

        Returns:
            The active collection ID

        Raises:
            ValueError: If collection_id provided but not found
        """
        if collection_id is not None:
            collection = self.get(collection_id)
            if not collection:
                raise ValueError(f"Collection '{collection_id}' not found")

            collection.increment_use()
            self._save_collections()

        # Save active collection
        if collection_id is None:
            if self.active_collection_path.exists():
                self.active_collection_path.unlink()
        else:
            with open(self.active_collection_path, "w", encoding="utf-8") as f:
                f.write(collection_id)

        return collection_id

    def get_active_collection(self) -> Optional[str]:
        """Get the active collection ID.

        Returns:
            The active collection ID or None
        """
        if not self.active_collection_path.exists():
            return None

        try:
            with open(self.active_collection_path, "r", encoding="utf-8") as f:
                collection_id = f.read().strip()
                # Verify it still exists
                if collection_id in self.collections:
                    return collection_id
                else:
                    # Clean up invalid reference
                    self.active_collection_path.unlink()
                    return None
        except Exception:
            return None

    # Statistics

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics.

        Returns:
            Dictionary with statistics
        """
        collections = list(self.collections.values())
        active_collections = [c for c in collections if not c.is_archived]
        archived_collections = [c for c in collections if c.is_archived]

        total_prompts = sum(len(c.prompts) for c in collections)
        total_templates = sum(len(c.templates) for c in collections)
        total_snippets = sum(len(c.snippets) for c in collections)

        most_used = sorted(collections, key=lambda c: c.use_count, reverse=True)[:5]

        return {
            "total_collections": len(collections),
            "active_collections": len(active_collections),
            "archived_collections": len(archived_collections),
            "total_prompts": total_prompts,
            "total_templates": total_templates,
            "total_snippets": total_snippets,
            "most_used": [
                {
                    "id": c.id,
                    "name": c.name,
                    "use_count": c.use_count,
                    "items": len(c.prompts) + len(c.templates) + len(c.snippets),
                }
                for c in most_used
            ],
            "active_collection": self.get_active_collection(),
        }

    # Export/Import

    def export_collection(
        self, collection_id: str, include_content: bool = False
    ) -> Dict[str, Any]:
        """Export a collection to a dictionary.

        Args:
            collection_id: The collection ID
            include_content: If True, include actual content of items
                           (requires access to other managers)

        Returns:
            Dictionary with collection data

        Raises:
            ValueError: If collection not found
        """
        collection = self.get(collection_id)
        if not collection:
            raise ValueError(f"Collection '{collection_id}' not found")

        export_data = collection.to_dict()
        export_data["exported_at"] = datetime.now().isoformat()
        export_data["format_version"] = "1.0"

        # Note: Content export would require integration with other managers
        # For now, we just export the IDs
        if include_content:
            export_data["_note"] = (
                "Content export requires integration with history, templates, and snippets managers"
            )

        return export_data

    def import_collection(self, data: Dict[str, Any], overwrite: bool = False) -> Collection:
        """Import a collection from a dictionary.

        Args:
            data: The collection data
            overwrite: If True, overwrite existing collection with same ID

        Returns:
            The imported collection

        Raises:
            ValueError: If collection exists and overwrite is False
        """
        collection_id = data.get("id")
        if not collection_id:
            raise ValueError("Missing 'id' in import data")

        if collection_id in self.collections and not overwrite:
            raise ValueError(
                f"Collection '{collection_id}' already exists. Use overwrite=True to replace."
            )

        # Remove export metadata
        data.pop("exported_at", None)
        data.pop("format_version", None)
        data.pop("_note", None)

        collection = Collection.from_dict(data)
        self.collections[collection_id] = collection
        self._save_collections()
        return collection

    def clear(self) -> None:
        """Clear all collections. Use with caution!"""
        self.collections.clear()
        self._save_collections()
        if self.active_collection_path.exists():
            self.active_collection_path.unlink()


# Singleton instance
_collections_manager: Optional[CollectionsManager] = None


def get_collections_manager() -> CollectionsManager:
    """Get the global collections manager instance.

    Returns:
        The CollectionsManager singleton
    """
    global _collections_manager
    if _collections_manager is None:
        _collections_manager = CollectionsManager()
    return _collections_manager
