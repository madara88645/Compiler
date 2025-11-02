"""Tests for template gallery."""

import json
from pathlib import Path

import pytest
import yaml

from app.template_gallery import GalleryTemplate, TemplateGallery, get_gallery


@pytest.fixture
def sample_template():
    """Create a sample gallery template."""
    return GalleryTemplate(
        id="test-template",
        name="Test Template",
        description="A test template for unit testing",
        category="test",
        tags=["test", "example", "demo"],
        difficulty="intermediate",
        author="Test Author",
        version="1.0",
        template={"persona": "test expert", "intent": "testing"},
        examples=["Example 1", "Example 2"],
        use_cases=["Testing", "Development"],
    )


@pytest.fixture
def temp_gallery_dir(tmp_path):
    """Create a temporary gallery directory."""
    gallery_dir = tmp_path / "gallery"
    gallery_dir.mkdir()
    return gallery_dir


class TestGalleryTemplate:
    """Tests for GalleryTemplate class."""

    def test_template_creation(self, sample_template):
        """Test creating a template."""
        assert sample_template.id == "test-template"
        assert sample_template.name == "Test Template"
        assert sample_template.category == "test"
        assert len(sample_template.tags) == 3
        assert sample_template.difficulty == "intermediate"

    def test_matches_search_by_name(self, sample_template):
        """Test search matching by name."""
        assert sample_template.matches_search("test")
        assert sample_template.matches_search("TEST")
        assert sample_template.matches_search("Template")
        assert not sample_template.matches_search("nonexistent")

    def test_matches_search_by_description(self, sample_template):
        """Test search matching by description."""
        assert sample_template.matches_search("unit testing")
        assert sample_template.matches_search("UNIT")

    def test_matches_search_by_category(self, sample_template):
        """Test search matching by category."""
        assert sample_template.matches_search("test")

    def test_matches_search_by_tags(self, sample_template):
        """Test search matching by tags."""
        assert sample_template.matches_search("example")
        assert sample_template.matches_search("demo")
        assert sample_template.matches_search("DEMO")

    def test_to_dict(self, sample_template):
        """Test converting template to dictionary."""
        data = sample_template.to_dict()

        assert data["id"] == "test-template"
        assert data["name"] == "Test Template"
        assert data["category"] == "test"
        assert data["tags"] == ["test", "example", "demo"]
        assert data["template"]["persona"] == "test expert"


class TestTemplateGallery:
    """Tests for TemplateGallery class."""

    def test_gallery_initialization(self, temp_gallery_dir):
        """Test gallery initialization."""
        gallery = TemplateGallery(temp_gallery_dir)

        assert gallery.gallery_dir == temp_gallery_dir
        assert len(gallery.templates) > 0  # Should have built-in templates

    def test_builtin_templates_loaded(self, temp_gallery_dir):
        """Test that built-in templates are loaded."""
        gallery = TemplateGallery(temp_gallery_dir)

        # Check for some built-in templates
        assert "tutorial-python" in gallery.templates
        assert "api-documentation" in gallery.templates
        assert "creative-story" in gallery.templates

    def test_list_all_templates(self, temp_gallery_dir):
        """Test listing all templates."""
        gallery = TemplateGallery(temp_gallery_dir)
        templates = gallery.list_templates()

        assert len(templates) > 0
        # Should be sorted by category and name
        assert templates == sorted(templates, key=lambda t: (t.category, t.name))

    def test_list_by_category(self, temp_gallery_dir):
        """Test filtering by category."""
        gallery = TemplateGallery(temp_gallery_dir)
        templates = gallery.list_templates(category="tutorial")

        assert len(templates) > 0
        assert all(t.category == "tutorial" for t in templates)

    def test_list_by_difficulty(self, temp_gallery_dir):
        """Test filtering by difficulty."""
        gallery = TemplateGallery(temp_gallery_dir)
        templates = gallery.list_templates(difficulty="beginner")

        assert len(templates) > 0
        assert all(t.difficulty == "beginner" for t in templates)

    def test_list_by_tags(self, temp_gallery_dir):
        """Test filtering by tags."""
        gallery = TemplateGallery(temp_gallery_dir)
        templates = gallery.list_templates(tags=["python"])

        assert len(templates) > 0
        assert all(any("python" in tag for tag in t.tags) for t in templates)

    def test_search_templates(self, temp_gallery_dir):
        """Test searching templates."""
        gallery = TemplateGallery(temp_gallery_dir)
        results = gallery.search_templates("python")

        assert len(results) > 0
        # Check that results match the search query
        for template in results:
            assert template.matches_search("python")

    def test_search_no_results(self, temp_gallery_dir):
        """Test search with no results."""
        gallery = TemplateGallery(temp_gallery_dir)
        results = gallery.search_templates("nonexistent-query-xyz")

        assert len(results) == 0

    def test_get_template(self, temp_gallery_dir):
        """Test getting template by ID."""
        gallery = TemplateGallery(temp_gallery_dir)
        template = gallery.get_template("tutorial-python")

        assert template is not None
        assert template.id == "tutorial-python"
        assert template.name == "Python Tutorial"

    def test_get_nonexistent_template(self, temp_gallery_dir):
        """Test getting non-existent template."""
        gallery = TemplateGallery(temp_gallery_dir)
        template = gallery.get_template("nonexistent-id")

        assert template is None

    def test_get_categories(self, temp_gallery_dir):
        """Test getting all categories."""
        gallery = TemplateGallery(temp_gallery_dir)
        categories = gallery.get_categories()

        assert len(categories) > 0
        assert "tutorial" in categories
        assert "documentation" in categories
        assert categories == sorted(categories)

    def test_add_custom_template(self, temp_gallery_dir, sample_template):
        """Test adding a custom template."""
        gallery = TemplateGallery(temp_gallery_dir)
        gallery.add_custom_template(sample_template)

        # Verify it's in memory
        assert sample_template.id in gallery.templates

        # Verify it's saved to file
        template_file = temp_gallery_dir / f"{sample_template.id}.yaml"
        assert template_file.exists()

        # Verify file content
        with open(template_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["id"] == sample_template.id

    def test_remove_custom_template(self, temp_gallery_dir, sample_template):
        """Test removing a custom template."""
        gallery = TemplateGallery(temp_gallery_dir)

        # Add template first
        gallery.add_custom_template(sample_template)
        assert sample_template.id in gallery.templates

        # Remove it
        success = gallery.remove_custom_template(sample_template.id)
        assert success is True
        assert sample_template.id not in gallery.templates

        # Verify file is deleted
        template_file = temp_gallery_dir / f"{sample_template.id}.yaml"
        assert not template_file.exists()

    def test_remove_nonexistent_template(self, temp_gallery_dir):
        """Test removing non-existent template."""
        gallery = TemplateGallery(temp_gallery_dir)
        success = gallery.remove_custom_template("nonexistent-id")

        assert success is False

    def test_export_template(self, temp_gallery_dir, tmp_path):
        """Test exporting a template."""
        gallery = TemplateGallery(temp_gallery_dir)
        output_path = tmp_path / "exported.yaml"

        success = gallery.export_template("tutorial-python", output_path)

        assert success is True
        assert output_path.exists()

        # Verify content
        with open(output_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["id"] == "tutorial-python"

    def test_export_nonexistent_template(self, temp_gallery_dir, tmp_path):
        """Test exporting non-existent template."""
        gallery = TemplateGallery(temp_gallery_dir)
        output_path = tmp_path / "exported.yaml"

        success = gallery.export_template("nonexistent-id", output_path)

        assert success is False

    def test_import_template(self, temp_gallery_dir, sample_template, tmp_path):
        """Test importing a template."""
        # Create a template file
        template_file = tmp_path / "import_test.yaml"
        with open(template_file, "w", encoding="utf-8") as f:
            yaml.dump(sample_template.to_dict(), f)

        gallery = TemplateGallery(temp_gallery_dir)
        imported = gallery.import_template(template_file)

        assert imported is not None
        assert imported.id == sample_template.id
        assert sample_template.id in gallery.templates

    def test_import_invalid_template(self, temp_gallery_dir, tmp_path):
        """Test importing invalid template file."""
        # Create invalid file
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("invalid: yaml: content: [[[")

        gallery = TemplateGallery(temp_gallery_dir)
        imported = gallery.import_template(invalid_file)

        assert imported is None

    def test_get_template_preview(self, temp_gallery_dir):
        """Test getting template preview."""
        gallery = TemplateGallery(temp_gallery_dir)
        preview = gallery.get_template_preview("tutorial-python")

        assert preview is not None
        assert "# Python Tutorial" in preview
        assert "## Description" in preview
        assert "## Use Cases" in preview
        assert "## Examples" in preview
        assert "## Template Fields" in preview
        assert "```yaml" in preview

    def test_get_preview_nonexistent(self, temp_gallery_dir):
        """Test getting preview for non-existent template."""
        gallery = TemplateGallery(temp_gallery_dir)
        preview = gallery.get_template_preview("nonexistent-id")

        assert preview is None

    def test_template_persistence(self, temp_gallery_dir, sample_template):
        """Test that custom templates persist across gallery instances."""
        # Create gallery and add template
        gallery1 = TemplateGallery(temp_gallery_dir)
        gallery1.add_custom_template(sample_template)

        # Create new gallery instance (should reload from disk)
        gallery2 = TemplateGallery(temp_gallery_dir)
        assert sample_template.id in gallery2.templates

        # Verify template data
        loaded = gallery2.get_template(sample_template.id)
        assert loaded is not None
        assert loaded.name == sample_template.name


class TestGetGallery:
    """Tests for get_gallery function."""

    def test_get_default_gallery(self):
        """Test getting default gallery."""
        gallery = get_gallery()

        assert isinstance(gallery, TemplateGallery)
        assert len(gallery.templates) > 0

    def test_get_gallery_with_custom_dir(self, temp_gallery_dir):
        """Test getting gallery with custom directory."""
        gallery = get_gallery(temp_gallery_dir)

        assert isinstance(gallery, TemplateGallery)
        assert gallery.gallery_dir == temp_gallery_dir

    def test_gallery_singleton(self):
        """Test that get_gallery returns same instance."""
        gallery1 = get_gallery()
        gallery2 = get_gallery()

        # Should be same instance when no custom dir is provided
        assert gallery1 is gallery2


class TestGalleryIntegration:
    """Integration tests for gallery functionality."""

    def test_full_workflow(self, temp_gallery_dir, sample_template, tmp_path):
        """Test complete gallery workflow."""
        gallery = TemplateGallery(temp_gallery_dir)

        # List templates
        all_templates = gallery.list_templates()
        initial_count = len(all_templates)

        # Add custom template
        gallery.add_custom_template(sample_template)
        assert len(gallery.list_templates()) == initial_count + 1

        # Search for template
        results = gallery.search_templates("test")
        assert any(t.id == sample_template.id for t in results)

        # Get preview
        preview = gallery.get_template_preview(sample_template.id)
        assert preview is not None

        # Export template
        export_path = tmp_path / "exported.yaml"
        assert gallery.export_template(sample_template.id, export_path)

        # Remove template
        assert gallery.remove_custom_template(sample_template.id)
        assert len(gallery.list_templates()) == initial_count

        # Import template back
        imported = gallery.import_template(export_path)
        assert imported is not None
        assert len(gallery.list_templates()) == initial_count + 1
