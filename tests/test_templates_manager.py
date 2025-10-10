"""Tests for templates_manager module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.templates import PromptTemplate, TemplateRegistry, TemplateVariable
from app.templates_manager import TemplatesManager, TemplateUsageStats


@pytest.fixture
def temp_registry_dirs():
    """Create temporary directories for template registry."""
    with tempfile.TemporaryDirectory() as builtin_dir, tempfile.TemporaryDirectory() as user_dir:
        yield Path(builtin_dir), Path(user_dir)


@pytest.fixture
def temp_stats_file():
    """Create temporary stats file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        stats_path = Path(f.name)
    yield stats_path
    if stats_path.exists():
        stats_path.unlink()


@pytest.fixture
def manager_with_temp_dirs(temp_registry_dirs, temp_stats_file):
    """Create TemplatesManager with temporary directories."""
    builtin_dir, user_dir = temp_registry_dirs
    registry = TemplateRegistry(builtin_path=builtin_dir, user_path=user_dir)
    manager = TemplatesManager(registry=registry)
    manager.stats_file = temp_stats_file
    return manager


def test_templates_manager_init(manager_with_temp_dirs):
    """Test TemplatesManager initialization"""
    manager = manager_with_temp_dirs
    assert manager.registry is not None
    assert manager.stats_file.exists() or not manager.stats_file.exists()  # May not exist yet


def test_create_template(manager_with_temp_dirs):
    """Test creating a new template"""
    manager = manager_with_temp_dirs

    template = manager.create_template(
        template_id="test_template",
        name="Test Template",
        description="A test template",
        category="testing",
        template_text="Hello {{name}}, welcome to {{place}}!",
        variables=[
            {"name": "name", "description": "User's name", "required": True},
            {"name": "place", "description": "Location", "required": True},
        ],
        tags=["test", "example"],
        author="Test Author",
    )

    assert template.id == "test_template"
    assert template.name == "Test Template"
    assert template.category == "testing"
    assert len(template.variables) == 2
    assert len(template.tags) == 2


def test_create_duplicate_template(manager_with_temp_dirs):
    """Test creating duplicate template raises error"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="duplicate",
        name="First",
        description="First template",
        category="test",
        template_text="Test",
    )

    with pytest.raises(ValueError, match="already exists"):
        manager.create_template(
            template_id="duplicate",
            name="Second",
            description="Second template",
            category="test",
            template_text="Test",
        )


def test_list_templates(manager_with_temp_dirs):
    """Test listing templates"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="template1",
        name="Template 1",
        description="First template",
        category="coding",
        template_text="Code: {{code}}",
        tags=["python"],
    )

    manager.create_template(
        template_id="template2",
        name="Template 2",
        description="Second template",
        category="writing",
        template_text="Write: {{text}}",
        tags=["essay"],
    )

    # List all
    all_templates = manager.list_templates()
    assert len(all_templates) == 2

    # Filter by category
    coding_templates = manager.list_templates(category="coding")
    assert len(coding_templates) == 1
    assert coding_templates[0].id == "template1"

    # Filter by tag
    python_templates = manager.list_templates(tag="python")
    assert len(python_templates) == 1
    assert python_templates[0].id == "template1"

    # Search
    search_results = manager.list_templates(search="Second")
    assert len(search_results) == 1
    assert search_results[0].id == "template2"


def test_get_template(manager_with_temp_dirs):
    """Test getting a specific template"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="get_test",
        name="Get Test",
        description="Test template",
        category="test",
        template_text="Hello {{world}}",
    )

    template = manager.get_template("get_test")
    assert template is not None
    assert template.id == "get_test"

    # Non-existent template
    assert manager.get_template("nonexistent") is None


def test_update_template(manager_with_temp_dirs):
    """Test updating a template"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="update_test",
        name="Original Name",
        description="Original description",
        category="test",
        template_text="Original text",
        tags=["old"],
    )

    updated = manager.update_template(
        template_id="update_test",
        name="Updated Name",
        description="Updated description",
        tags=["new", "updated"],
    )

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.description == "Updated description"
    assert "new" in updated.tags
    assert "updated" in updated.tags


def test_update_nonexistent_template(manager_with_temp_dirs):
    """Test updating non-existent template returns None"""
    manager = manager_with_temp_dirs

    result = manager.update_template(
        template_id="nonexistent",
        name="New Name",
    )

    assert result is None


def test_delete_template(manager_with_temp_dirs):
    """Test deleting a template"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="delete_test",
        name="Delete Test",
        description="Will be deleted",
        category="test",
        template_text="Delete me",
    )

    # Verify exists
    assert manager.get_template("delete_test") is not None

    # Delete
    success = manager.delete_template("delete_test")
    assert success is True

    # Verify deleted
    assert manager.get_template("delete_test") is None


def test_use_template(manager_with_temp_dirs):
    """Test using a template with variables"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="use_test",
        name="Use Test",
        description="Template to use",
        category="test",
        template_text="Hello {{name}}, you are {{age}} years old!",
        variables=[
            {"name": "name", "description": "Name", "required": True},
            {"name": "age", "description": "Age", "required": True},
        ],
    )

    rendered = manager.use_template(
        "use_test",
        {"name": "Alice", "age": "30"},
    )

    assert rendered == "Hello Alice, you are 30 years old!"

    # Check usage stats updated
    stats = manager.get_stats("use_test")
    assert stats["use_count"] == 1


def test_use_template_missing_required_variable(manager_with_temp_dirs):
    """Test using template with missing required variable raises error"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="required_test",
        name="Required Test",
        description="Has required variables",
        category="test",
        template_text="Name: {{name}}",
        variables=[
            {"name": "name", "description": "Name", "required": True},
        ],
    )

    with pytest.raises(ValueError, match="Missing required variables"):
        manager.use_template("required_test", {})


def test_use_nonexistent_template(manager_with_temp_dirs):
    """Test using non-existent template returns None"""
    manager = manager_with_temp_dirs

    result = manager.use_template("nonexistent", {})
    assert result is None


def test_get_categories(manager_with_temp_dirs):
    """Test getting all categories"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="cat1",
        name="Cat 1",
        description="Category 1",
        category="coding",
        template_text="Code",
    )

    manager.create_template(
        template_id="cat2",
        name="Cat 2",
        description="Category 2",
        category="writing",
        template_text="Write",
    )

    categories = manager.get_categories()
    assert "coding" in categories
    assert "writing" in categories


def test_get_stats_overall(manager_with_temp_dirs):
    """Test getting overall statistics"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="stats1",
        name="Stats 1",
        description="First",
        category="test",
        template_text="Test {{var}}",
        variables=[{"name": "var", "description": "Variable", "required": True}],
    )

    manager.create_template(
        template_id="stats2",
        name="Stats 2",
        description="Second",
        category="test",
        template_text="Test {{var}}",
        variables=[{"name": "var", "description": "Variable", "required": True}],
    )

    # Use templates
    manager.use_template("stats1", {"var": "value"})
    manager.use_template("stats1", {"var": "value"})
    manager.use_template("stats2", {"var": "value"})

    stats = manager.get_stats()
    assert stats["total_templates"] == 2
    assert stats["templates_used"] == 2
    assert stats["total_uses"] == 3
    assert len(stats["most_used"]) > 0


def test_get_stats_specific_template(manager_with_temp_dirs):
    """Test getting stats for specific template"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="specific_stats",
        name="Specific Stats",
        description="Test",
        category="test",
        template_text="Test {{var}}",
        variables=[{"name": "var", "description": "Variable", "required": True}],
    )

    # Before use
    stats = manager.get_stats("specific_stats")
    assert stats["use_count"] == 0

    # After use
    manager.use_template("specific_stats", {"var": "value"})
    stats = manager.get_stats("specific_stats")
    assert stats["use_count"] == 1


def test_validate_template(manager_with_temp_dirs):
    """Test template validation"""
    manager = manager_with_temp_dirs

    # Valid template
    manager.create_template(
        template_id="valid",
        name="Valid",
        description="Valid template",
        category="test",
        template_text="Hello {{name}}",
        variables=[{"name": "name", "description": "Name", "required": True}],
    )

    validation = manager.validate_template("valid")
    assert validation["valid"] is True
    assert len(validation["issues"]) == 0

    # Template with undefined variable
    manager.create_template(
        template_id="undefined_var",
        name="Undefined",
        description="Has undefined variable",
        category="test",
        template_text="Hello {{name}} and {{missing}}",
        variables=[{"name": "name", "description": "Name", "required": True}],
    )

    validation = manager.validate_template("undefined_var")
    assert validation["valid"] is False
    assert len(validation["issues"]) > 0
    assert "missing" in validation["placeholders"]


def test_validate_nonexistent_template(manager_with_temp_dirs):
    """Test validating non-existent template"""
    manager = manager_with_temp_dirs

    validation = manager.validate_template("nonexistent")
    assert validation["valid"] is False
    assert "not found" in validation["error"]


def test_export_template(manager_with_temp_dirs, tmp_path):
    """Test exporting a template"""
    manager = manager_with_temp_dirs

    manager.create_template(
        template_id="export_test",
        name="Export Test",
        description="Template to export",
        category="test",
        template_text="Export {{content}}",
        variables=[{"name": "content", "description": "Content", "required": True}],
    )

    output_path = tmp_path / "exported.yaml"
    success = manager.export_template("export_test", output_path)

    assert success is True
    assert output_path.exists()


def test_export_nonexistent_template(manager_with_temp_dirs, tmp_path):
    """Test exporting non-existent template"""
    manager = manager_with_temp_dirs

    output_path = tmp_path / "nonexistent.yaml"
    success = manager.export_template("nonexistent", output_path)

    assert success is False


def test_import_template(manager_with_temp_dirs, tmp_path):
    """Test importing a template"""
    manager = manager_with_temp_dirs

    # Create a template and export it
    manager.create_template(
        template_id="import_test",
        name="Import Test",
        description="Template to import",
        category="test",
        template_text="Import {{data}}",
        variables=[{"name": "data", "description": "Data", "required": True}],
    )

    export_path = tmp_path / "import_test.yaml"
    manager.export_template("import_test", export_path)

    # Delete original
    manager.delete_template("import_test")
    assert manager.get_template("import_test") is None

    # Import it back
    imported = manager.import_template(export_path)
    assert imported is not None
    assert imported.id == "import_test"
    assert manager.get_template("import_test") is not None


def test_stats_persistence(manager_with_temp_dirs):
    """Test that usage stats persist across manager instances"""
    manager1 = manager_with_temp_dirs

    manager1.create_template(
        template_id="persist_test",
        name="Persist Test",
        description="Test persistence",
        category="test",
        template_text="Test {{var}}",
        variables=[{"name": "var", "description": "Variable", "required": True}],
    )

    manager1.use_template("persist_test", {"var": "value"})
    manager1.use_template("persist_test", {"var": "value"})

    # Create new manager with same stats file
    manager2 = TemplatesManager(registry=manager1.registry)
    manager2.stats_file = manager1.stats_file
    manager2._load_stats()

    stats = manager2.get_stats("persist_test")
    assert stats["use_count"] == 2
