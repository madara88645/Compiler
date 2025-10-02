"""Tests for template system."""

from __future__ import annotations

import pytest
from pathlib import Path

from app.templates import (
    PromptTemplate,
    TemplateVariable,
    TemplateRegistry,
    get_registry,
    reset_registry,
)


@pytest.fixture
def builtin_templates_path():
    """Get the path to built-in templates."""
    # Use the project root templates directory
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    return project_root / "templates"


@pytest.fixture
def temp_template_dir(tmp_path):
    """Create temporary template directory."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    return template_dir


@pytest.fixture
def sample_template():
    """Create a sample template for testing."""
    return PromptTemplate(
        id="test-template",
        name="Test Template",
        description="A test template",
        category="testing",
        template_text="Hello {{name}}, your level is {{level}}.",
        variables=[
            TemplateVariable(name="name", description="User name", required=True),
            TemplateVariable(
                name="level", description="User level", default="beginner", required=False
            ),
        ],
        tags=["test"],
    )


def test_template_render_with_all_variables(sample_template):
    """Test rendering template with all variables provided."""
    result = sample_template.render({"name": "Alice", "level": "advanced"})
    assert result == "Hello Alice, your level is advanced."


def test_template_render_with_default(sample_template):
    """Test rendering template using default value."""
    result = sample_template.render({"name": "Bob"})
    assert result == "Hello Bob, your level is beginner."


def test_template_render_missing_required():
    """Test that missing required variables raise error."""
    template = PromptTemplate(
        id="test",
        name="Test",
        description="Test",
        category="test",
        template_text="Hello {{name}}",
        variables=[TemplateVariable(name="name", description="Name", required=True)],
    )

    with pytest.raises(ValueError, match="Missing required variables: name"):
        template.render({})


def test_template_to_dict_and_from_dict(sample_template):
    """Test serialization round-trip."""
    data = sample_template.to_dict()
    restored = PromptTemplate.from_dict(data)

    assert restored.id == sample_template.id
    assert restored.name == sample_template.name
    assert restored.template_text == sample_template.template_text
    assert len(restored.variables) == len(sample_template.variables)
    assert restored.variables[0].name == sample_template.variables[0].name


def test_registry_load_builtin_templates(builtin_templates_path):
    """Test loading built-in templates."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)
    templates = registry.list_templates()

    # Should have at least the templates we created
    assert len(templates) >= 5
    template_ids = {t.id for t in templates}
    assert "code-review" in template_ids
    assert "tutorial-creator" in template_ids
    assert "tech-comparison" in template_ids


def test_registry_filter_by_category(builtin_templates_path):
    """Test filtering templates by category."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    dev_templates = registry.list_templates(category="development")
    assert all(t.category == "development" for t in dev_templates)
    assert len(dev_templates) >= 2  # code-review and bug-analyzer


def test_registry_get_template(builtin_templates_path):
    """Test retrieving specific template."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    template = registry.get_template("code-review")
    assert template is not None
    assert template.id == "code-review"
    assert template.name == "Code Review"
    assert len(template.variables) > 0


def test_registry_get_nonexistent_template(builtin_templates_path):
    """Test getting template that doesn't exist."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    template = registry.get_template("nonexistent-id")
    assert template is None


def test_registry_get_categories(builtin_templates_path):
    """Test getting all categories."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    categories = registry.get_categories()
    assert "development" in categories
    assert "education" in categories
    assert "analysis" in categories
    assert "documentation" in categories


def test_registry_save_and_load_user_template(builtin_templates_path, temp_template_dir, sample_template):
    """Test saving and loading user templates."""
    registry = TemplateRegistry(
        builtin_path=builtin_templates_path,
        user_path=temp_template_dir,
    )

    # Save template
    saved_path = registry.save_template(sample_template, user_template=True)
    assert saved_path.exists()
    assert saved_path.parent == temp_template_dir

    # Reload registry
    registry2 = TemplateRegistry(
        builtin_path=builtin_templates_path,
        user_path=temp_template_dir,
    )

    loaded = registry2.get_template("test-template")
    assert loaded is not None
    assert loaded.name == sample_template.name


def test_registry_delete_template(builtin_templates_path, temp_template_dir, sample_template):
    """Test deleting user templates."""
    registry = TemplateRegistry(
        builtin_path=builtin_templates_path,
        user_path=temp_template_dir,
    )

    # Save and delete
    registry.save_template(sample_template, user_template=True)
    assert registry.get_template("test-template") is not None

    success = registry.delete_template("test-template", user_only=True)
    assert success
    assert registry.get_template("test-template") is None


def test_code_review_template_render(builtin_templates_path):
    """Test rendering the built-in code-review template."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    template = registry.get_template("code-review")
    assert template is not None

    result = template.render(
        {
            "language": "Python",
            "context": "REST API authentication",
        }
    )

    assert "Python" in result
    assert "REST API authentication" in result
    assert "code quality" in result.lower()


def test_tutorial_creator_template_render(builtin_templates_path):
    """Test rendering the tutorial-creator template."""
    registry = TemplateRegistry(builtin_path=builtin_templates_path)

    template = registry.get_template("tutorial-creator")
    assert template is not None

    result = template.render(
        {
            "topic": "Docker basics",
            "level": "beginner",
            "duration": "30 minutes",
        }
    )

    assert "Docker basics" in result
    assert "beginner" in result
    assert "30 minutes" in result
    assert "tutorial" in result.lower()
