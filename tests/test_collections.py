"""Tests for collections/workspaces module."""

import pytest
import json
from pathlib import Path
from app.collections import (
    Collection,
    CollectionsManager,
    get_collections_manager,
)


@pytest.fixture
def temp_storage(tmp_path):
    """Temporary storage path for testing."""
    return tmp_path / "collections.json"


@pytest.fixture
def temp_active_path(tmp_path):
    """Temporary active collection path for testing."""
    return tmp_path / "active_collection.txt"


@pytest.fixture
def manager(temp_storage, temp_active_path, monkeypatch):
    """Create a collections manager with temporary storage."""
    mgr = CollectionsManager(storage_path=temp_storage)
    # Override active collection path
    monkeypatch.setattr(mgr, "active_collection_path", temp_active_path)
    return mgr


def test_collection_creation():
    """Test Collection dataclass creation."""
    collection = Collection(
        id="proj1",
        name="My Project",
        description="Test project",
        tags=["work", "important"],
        color="green",
    )
    assert collection.id == "proj1"
    assert collection.name == "My Project"
    assert collection.description == "Test project"
    assert collection.tags == ["work", "important"]
    assert collection.color == "green"
    assert collection.is_archived is False
    assert collection.use_count == 0
    assert collection.last_used is None


def test_collection_to_dict():
    """Test Collection serialization."""
    collection = Collection(
        id="proj1",
        name="My Project",
        prompts=["p1", "p2"],
        templates=["t1"],
        snippets=["s1", "s2", "s3"],
    )
    data = collection.to_dict()
    assert data["id"] == "proj1"
    assert data["name"] == "My Project"
    assert data["prompts"] == ["p1", "p2"]
    assert data["templates"] == ["t1"]
    assert data["snippets"] == ["s1", "s2", "s3"]


def test_collection_from_dict():
    """Test Collection deserialization."""
    data = {
        "id": "proj1",
        "name": "My Project",
        "description": "Test",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-02T00:00:00",
        "prompts": ["p1"],
        "templates": ["t1"],
        "snippets": ["s1"],
        "tags": ["test"],
        "color": "blue",
        "is_archived": False,
        "use_count": 5,
        "last_used": "2024-01-02T00:00:00",
    }
    collection = Collection.from_dict(data)
    assert collection.id == "proj1"
    assert collection.name == "My Project"
    assert collection.use_count == 5
    assert len(collection.prompts) == 1


def test_collection_increment_use():
    """Test incrementing use count."""
    collection = Collection(id="proj1", name="Test")
    assert collection.use_count == 0
    assert collection.last_used is None

    collection.increment_use()
    assert collection.use_count == 1
    assert collection.last_used is not None

    collection.increment_use()
    assert collection.use_count == 2


def test_manager_initialization(manager):
    """Test manager initialization."""
    assert manager.collections == {}
    assert manager.storage_path.parent.exists()


def test_create_collection(manager):
    """Test creating a collection."""
    collection = manager.create(
        collection_id="proj1",
        name="Project 1",
        description="Test project",
        tags=["work"],
        color="green",
    )

    assert collection.id == "proj1"
    assert collection.name == "Project 1"
    assert collection.description == "Test project"
    assert collection.tags == ["work"]
    assert collection.color == "green"
    assert "proj1" in manager.collections


def test_create_duplicate_collection(manager):
    """Test creating a collection with duplicate ID."""
    manager.create("proj1", "Project 1")

    with pytest.raises(ValueError, match="already exists"):
        manager.create("proj1", "Another Project")


def test_get_collection(manager):
    """Test getting a collection."""
    manager.create("proj1", "Project 1")

    collection = manager.get("proj1")
    assert collection is not None
    assert collection.name == "Project 1"

    missing = manager.get("missing")
    assert missing is None


def test_get_all_collections(manager):
    """Test getting all collections."""
    manager.create("proj1", "Project 1", tags=["work"])
    manager.create("proj2", "Project 2", tags=["personal"])
    manager.create("proj3", "Project 3", tags=["work", "urgent"])

    # All collections
    all_collections = manager.get_all()
    assert len(all_collections) == 3

    # Filter by tag
    work_collections = manager.get_all(tag="work")
    assert len(work_collections) == 2

    urgent_collections = manager.get_all(tag="urgent")
    assert len(urgent_collections) == 1


def test_get_all_archived_filter(manager):
    """Test filtering by archived status."""
    manager.create("proj1", "Project 1")
    manager.create("proj2", "Project 2")

    manager.archive("proj1")

    # All collections
    all_collections = manager.get_all()
    assert len(all_collections) == 2

    # Active only
    active = manager.get_all(archived=False)
    assert len(active) == 1
    assert active[0].id == "proj2"

    # Archived only
    archived = manager.get_all(archived=True)
    assert len(archived) == 1
    assert archived[0].id == "proj1"


def test_update_collection(manager):
    """Test updating a collection."""
    manager.create("proj1", "Project 1", description="Original")

    updated = manager.update(
        "proj1",
        name="Updated Project",
        description="New description",
        tags=["new", "tags"],
        color="red",
    )

    assert updated.name == "Updated Project"
    assert updated.description == "New description"
    assert updated.tags == ["new", "tags"]
    assert updated.color == "red"


def test_update_nonexistent_collection(manager):
    """Test updating a collection that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        manager.update("missing", name="Updated")


def test_delete_collection(manager):
    """Test deleting a collection."""
    manager.create("proj1", "Project 1")
    assert "proj1" in manager.collections

    result = manager.delete("proj1")
    assert result is True
    assert "proj1" not in manager.collections

    # Delete non-existent
    result = manager.delete("missing")
    assert result is False


def test_delete_active_collection(manager):
    """Test deleting the active collection clears active status."""
    manager.create("proj1", "Project 1")
    manager.set_active_collection("proj1")

    assert manager.get_active_collection() == "proj1"

    manager.delete("proj1")
    assert manager.get_active_collection() is None


def test_archive_unarchive(manager):
    """Test archiving and unarchiving collections."""
    manager.create("proj1", "Project 1")

    # Archive
    archived = manager.archive("proj1")
    assert archived.is_archived is True

    # Unarchive
    unarchived = manager.unarchive("proj1")
    assert unarchived.is_archived is False


def test_add_prompt(manager):
    """Test adding a prompt to a collection."""
    manager.create("proj1", "Project 1")

    collection = manager.add_prompt("proj1", "prompt_hash_123")
    assert "prompt_hash_123" in collection.prompts

    # Add same prompt again (should not duplicate)
    collection = manager.add_prompt("proj1", "prompt_hash_123")
    assert collection.prompts.count("prompt_hash_123") == 1


def test_add_template(manager):
    """Test adding a template to a collection."""
    manager.create("proj1", "Project 1")

    collection = manager.add_template("proj1", "template1")
    assert "template1" in collection.templates

    collection = manager.add_template("proj1", "template2")
    assert len(collection.templates) == 2


def test_add_snippet(manager):
    """Test adding a snippet to a collection."""
    manager.create("proj1", "Project 1")

    collection = manager.add_snippet("proj1", "snippet1")
    assert "snippet1" in collection.snippets


def test_add_item_to_nonexistent_collection(manager):
    """Test adding items to non-existent collection."""
    with pytest.raises(ValueError, match="not found"):
        manager.add_prompt("missing", "prompt1")

    with pytest.raises(ValueError, match="not found"):
        manager.add_template("missing", "template1")

    with pytest.raises(ValueError, match="not found"):
        manager.add_snippet("missing", "snippet1")


def test_remove_prompt(manager):
    """Test removing a prompt from a collection."""
    manager.create("proj1", "Project 1")
    manager.add_prompt("proj1", "prompt1")
    manager.add_prompt("proj1", "prompt2")

    collection = manager.remove_prompt("proj1", "prompt1")
    assert "prompt1" not in collection.prompts
    assert "prompt2" in collection.prompts


def test_remove_template(manager):
    """Test removing a template from a collection."""
    manager.create("proj1", "Project 1")
    manager.add_template("proj1", "template1")

    collection = manager.remove_template("proj1", "template1")
    assert "template1" not in collection.templates


def test_remove_snippet(manager):
    """Test removing a snippet from a collection."""
    manager.create("proj1", "Project 1")
    manager.add_snippet("proj1", "snippet1")

    collection = manager.remove_snippet("proj1", "snippet1")
    assert "snippet1" not in collection.snippets


def test_set_active_collection(manager):
    """Test setting active collection."""
    manager.create("proj1", "Project 1")
    manager.create("proj2", "Project 2")

    # Set active
    active_id = manager.set_active_collection("proj1")
    assert active_id == "proj1"
    assert manager.get_active_collection() == "proj1"

    # Check use count incremented
    collection = manager.get("proj1")
    assert collection.use_count == 1

    # Switch active
    manager.set_active_collection("proj2")
    assert manager.get_active_collection() == "proj2"

    # Clear active
    manager.set_active_collection(None)
    assert manager.get_active_collection() is None


def test_set_nonexistent_active_collection(manager):
    """Test setting non-existent collection as active."""
    with pytest.raises(ValueError, match="not found"):
        manager.set_active_collection("missing")


def test_get_stats(manager):
    """Test getting collection statistics."""
    manager.create("proj1", "Project 1")
    manager.create("proj2", "Project 2")
    manager.create("proj3", "Project 3")

    manager.add_prompt("proj1", "p1")
    manager.add_prompt("proj1", "p2")
    manager.add_template("proj1", "t1")
    manager.add_snippet("proj2", "s1")

    manager.archive("proj3")

    manager.set_active_collection("proj1")
    manager.set_active_collection("proj2")
    manager.set_active_collection("proj1")

    stats = manager.get_stats()

    assert stats["total_collections"] == 3
    assert stats["active_collections"] == 2
    assert stats["archived_collections"] == 1
    assert stats["total_prompts"] == 2
    assert stats["total_templates"] == 1
    assert stats["total_snippets"] == 1
    assert stats["active_collection"] == "proj1"

    # Most used
    assert len(stats["most_used"]) > 0
    assert stats["most_used"][0]["id"] == "proj1"
    assert stats["most_used"][0]["use_count"] == 2


def test_export_collection(manager):
    """Test exporting a collection."""
    manager.create("proj1", "Project 1", description="Test", tags=["work"])
    manager.add_prompt("proj1", "p1")
    manager.add_template("proj1", "t1")
    manager.add_snippet("proj1", "s1")

    export_data = manager.export_collection("proj1")

    assert export_data["id"] == "proj1"
    assert export_data["name"] == "Project 1"
    assert export_data["description"] == "Test"
    assert export_data["tags"] == ["work"]
    assert "p1" in export_data["prompts"]
    assert "t1" in export_data["templates"]
    assert "s1" in export_data["snippets"]
    assert "exported_at" in export_data
    assert "format_version" in export_data


def test_export_nonexistent_collection(manager):
    """Test exporting a collection that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        manager.export_collection("missing")


def test_import_collection(manager):
    """Test importing a collection."""
    data = {
        "id": "imported",
        "name": "Imported Project",
        "description": "Imported",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        "prompts": ["p1", "p2"],
        "templates": ["t1"],
        "snippets": ["s1"],
        "tags": ["imported"],
        "color": "purple",
        "is_archived": False,
        "use_count": 0,
        "last_used": None,
    }

    collection = manager.import_collection(data)

    assert collection.id == "imported"
    assert collection.name == "Imported Project"
    assert len(collection.prompts) == 2
    assert len(collection.templates) == 1
    assert len(collection.snippets) == 1
    assert "imported" in manager.collections


def test_import_collection_duplicate(manager):
    """Test importing a collection with existing ID."""
    manager.create("proj1", "Project 1")

    data = {
        "id": "proj1",
        "name": "Imported",
        "description": "",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        "prompts": [],
        "templates": [],
        "snippets": [],
        "tags": [],
        "color": "blue",
        "is_archived": False,
        "use_count": 0,
        "last_used": None,
    }

    # Without overwrite
    with pytest.raises(ValueError, match="already exists"):
        manager.import_collection(data, overwrite=False)

    # With overwrite
    collection = manager.import_collection(data, overwrite=True)
    assert collection.name == "Imported"


def test_import_collection_missing_id(manager):
    """Test importing collection without ID."""
    data = {"name": "No ID"}

    with pytest.raises(ValueError, match="Missing 'id'"):
        manager.import_collection(data)


def test_persistence(manager, temp_storage):
    """Test that collections persist across instances."""
    # Create collections
    manager.create("proj1", "Project 1")
    manager.add_prompt("proj1", "p1")

    # Create new manager instance with same storage
    manager2 = CollectionsManager(storage_path=temp_storage)

    # Check data persisted
    assert "proj1" in manager2.collections
    collection = manager2.get("proj1")
    assert collection.name == "Project 1"
    assert "p1" in collection.prompts


def test_active_collection_persistence(manager, temp_active_path):
    """Test that active collection persists."""
    manager.create("proj1", "Project 1")
    manager.set_active_collection("proj1")

    # Create new manager instance
    manager2 = CollectionsManager(storage_path=manager.storage_path)
    manager2.active_collection_path = temp_active_path

    # Check active collection persisted
    assert manager2.get_active_collection() == "proj1"


def test_active_collection_cleanup(manager, temp_active_path):
    """Test that invalid active collection is cleaned up."""
    manager.create("proj1", "Project 1")
    manager.set_active_collection("proj1")
    manager.delete("proj1")

    # Active should be cleared
    assert manager.get_active_collection() is None


def test_clear_all_collections(manager):
    """Test clearing all collections."""
    manager.create("proj1", "Project 1")
    manager.create("proj2", "Project 2")
    manager.set_active_collection("proj1")

    assert len(manager.collections) == 2

    manager.clear()

    assert len(manager.collections) == 0
    assert manager.get_active_collection() is None


def test_get_collections_manager_singleton():
    """Test that get_collections_manager returns a singleton."""
    mgr1 = get_collections_manager()
    mgr2 = get_collections_manager()
    assert mgr1 is mgr2


def test_update_timestamp(manager):
    """Test that update_timestamp is called on modifications."""
    collection = manager.create("proj1", "Project 1")
    original_updated = collection.updated_at

    # Small delay to ensure timestamp changes
    import time

    time.sleep(0.01)

    manager.update("proj1", name="Updated")
    updated_collection = manager.get("proj1")

    assert updated_collection.updated_at != original_updated


def test_collection_items_summary(manager):
    """Test getting summary of collection items."""
    manager.create("proj1", "Project 1")
    manager.add_prompt("proj1", "p1")
    manager.add_prompt("proj1", "p2")
    manager.add_template("proj1", "t1")
    manager.add_snippet("proj1", "s1")
    manager.add_snippet("proj1", "s2")
    manager.add_snippet("proj1", "s3")

    collection = manager.get("proj1")
    total_items = (
        len(collection.prompts)
        + len(collection.templates)
        + len(collection.snippets)
    )

    assert total_items == 6
    assert len(collection.prompts) == 2
    assert len(collection.templates) == 1
    assert len(collection.snippets) == 3
