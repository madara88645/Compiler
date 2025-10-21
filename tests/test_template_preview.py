"""Tests for template preview and variable filling."""

import pytest
from app.template_preview import TemplatePreview, get_template_preview
from app.templates_manager import get_templates_manager


@pytest.fixture
def preview():
    """Get template preview instance."""
    return get_template_preview()


@pytest.fixture
def templates():
    """Get templates manager instance."""
    return get_templates_manager()


@pytest.fixture
def sample_template(templates):
    """Create a sample template with variables."""
    templates.create_template(
        template_id="test-vars",
        name="Test Template",
        description="Template with variables",
        template_text="Hello {{name}}, you are {{age}} years old.",
        category="test",
        tags=["test", "variables"],
    )
    yield "test-vars"
    # Cleanup
    templates.delete_template("test-vars")


@pytest.fixture
def multi_var_template(templates):
    """Create a template with multiple variable occurrences."""
    templates.create_template(
        template_id="multi-vars",
        name="Multi Variable Template",
        description="Template with repeated variables",
        template_text="Dear {{name}},\n\nYour order #{{order_id}} is ready.\n\nThank you, {{name}}!",
        category="test",
        tags=["test"],
    )
    yield "multi-vars"
    templates.delete_template("multi-vars")


@pytest.fixture
def no_vars_template(templates):
    """Create a template without variables."""
    templates.create_template(
        template_id="no-vars",
        name="No Variables Template",
        description="Template without variables",
        template_text="This is a simple template without any variables.",
        category="test",
        tags=["test"],
    )
    yield "no-vars"
    templates.delete_template("no-vars")


def test_singleton_pattern():
    """Test that get_template_preview returns singleton instance."""
    preview1 = get_template_preview()
    preview2 = get_template_preview()
    assert preview1 is preview2


def test_extract_variables_single(preview):
    """Test extracting variables from template with single occurrence."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = preview.extract_variables(content)
    assert variables == ["name", "age"]


def test_extract_variables_multiple_occurrences(preview):
    """Test extracting variables with multiple occurrences."""
    content = "Hello {{name}}! Nice to meet you, {{name}}."
    variables = preview.extract_variables(content)
    # Should only return unique variable names
    assert variables == ["name"]


def test_extract_variables_mixed(preview):
    """Test extracting multiple variables with some repeating."""
    content = "Order {{order_id}} for {{customer}} is ready. Contact {{customer}} at {{email}}."
    variables = preview.extract_variables(content)
    assert variables == ["order_id", "customer", "email"]


def test_extract_variables_none(preview):
    """Test extracting variables from template without variables."""
    content = "This is a simple template without variables."
    variables = preview.extract_variables(content)
    assert variables == []


def test_extract_variables_edge_cases(preview):
    """Test variable extraction edge cases."""
    # Invalid format - should not match
    content = "{{}} {{ name}} {{name }} {name} {{ name }}"
    variables = preview.extract_variables(content)
    assert variables == []

    # Valid format
    content = "{{valid1}} {{valid2}}"
    variables = preview.extract_variables(content)
    assert variables == ["valid1", "valid2"]


def test_validate_variables_all_provided(preview):
    """Test validation when all variables are provided."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {"name": "John", "age": "25"}
    is_valid, missing = preview.validate_variables(content, variables)
    assert is_valid is True
    assert missing == []


def test_validate_variables_some_missing(preview):
    """Test validation when some variables are missing."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {"name": "John"}
    is_valid, missing = preview.validate_variables(content, variables)
    assert is_valid is False
    assert missing == ["age"]


def test_validate_variables_all_missing(preview):
    """Test validation when all variables are missing."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {}
    is_valid, missing = preview.validate_variables(content, variables)
    assert is_valid is False
    assert set(missing) == {"name", "age"}


def test_validate_variables_empty_values(preview):
    """Test validation treats empty string as missing."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {"name": "John", "age": ""}
    is_valid, missing = preview.validate_variables(content, variables)
    assert is_valid is False
    assert missing == ["age"]


def test_validate_variables_extra_provided(preview):
    """Test validation when extra variables are provided."""
    content = "Hello {{name}}!"
    variables = {"name": "John", "age": "25", "country": "USA"}
    is_valid, missing = preview.validate_variables(content, variables)
    # Should be valid even with extra variables
    assert is_valid is True
    assert missing == []


def test_fill_template_simple(preview):
    """Test filling template with simple variables."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {"name": "John", "age": "25"}
    result = preview.fill_template(content, variables)
    assert result == "Hello John, you are 25 years old."


def test_fill_template_multiple_occurrences(preview):
    """Test filling template where variable appears multiple times."""
    content = "Hello {{name}}! Nice to meet you, {{name}}."
    variables = {"name": "Alice"}
    result = preview.fill_template(content, variables)
    assert result == "Hello Alice! Nice to meet you, Alice."


def test_fill_template_partial(preview):
    """Test filling template with only some variables."""
    content = "Hello {{name}}, you are {{age}} years old."
    variables = {"name": "John"}
    result = preview.fill_template(content, variables)
    # Age should remain as placeholder
    assert result == "Hello John, you are {{age}} years old."


def test_fill_template_no_variables(preview):
    """Test filling template without any variables."""
    content = "This is a simple template."
    variables = {}
    result = preview.fill_template(content, variables)
    assert result == content


def test_fill_template_special_characters(preview):
    """Test filling template with special characters in values."""
    content = "Email: {{email}}, Price: {{price}}"
    variables = {"email": "user@example.com", "price": "$99.99"}
    result = preview.fill_template(content, variables)
    assert result == "Email: user@example.com, Price: $99.99"


def test_fill_template_multiline(preview):
    """Test filling template with multiline content."""
    content = "Dear {{name}},\n\nYour order #{{order_id}} is ready.\n\nThank you!"
    variables = {"name": "Alice", "order_id": "12345"}
    result = preview.fill_template(content, variables)
    assert result == "Dear Alice,\n\nYour order #12345 is ready.\n\nThank you!"


def test_preview_template_nonexistent(preview):
    """Test previewing non-existent template."""
    success, message = preview.preview_template("nonexistent-template")
    assert success is False
    assert "not found" in message.lower()


def test_preview_template_without_variables(preview, no_vars_template):
    """Test previewing template without variables."""
    success, message = preview.preview_template(no_vars_template)
    assert success is True


def test_preview_template_with_variables(preview, sample_template):
    """Test previewing template with variables."""
    success, message = preview.preview_template(sample_template)
    assert success is True


def test_preview_template_with_values(preview, sample_template):
    """Test previewing template with variable values."""
    variables = {"name": "John", "age": "25"}
    success, message = preview.preview_template(sample_template, variables)
    assert success is True


def test_preview_template_partial_values(preview, sample_template):
    """Test previewing template with partial variable values."""
    variables = {"name": "John"}
    success, message = preview.preview_template(sample_template, variables)
    # Should still succeed but show missing variables
    assert success is True


def test_interactive_fill_nonexistent(preview):
    """Test interactive fill with non-existent template."""
    success, content, variables = preview.interactive_fill("nonexistent-template")
    assert success is False
    assert "not found" in content.lower()
    assert variables == {}


def test_interactive_fill_no_variables(preview, no_vars_template, monkeypatch):
    """Test interactive fill with template that has no variables."""
    success, content, variables = preview.interactive_fill(no_vars_template)
    assert success is True
    assert content == "This is a simple template without any variables."
    assert variables == {}


def test_integration_full_workflow(preview, templates):
    """Test complete workflow: create, preview, fill template."""
    # Create template
    templates.create_template(
        template_id="workflow-test",
        name="Workflow Test",
        description="Integration test template",
        template_text="Product: {{product}}\nPrice: {{price}}\nQuantity: {{quantity}}",
        category="test",
        tags=["test"],
    )

    try:
        # Extract variables
        template = templates.get_template("workflow-test")
        variables = preview.extract_variables(template.template_text)
        assert len(variables) == 3
        assert set(variables) == {"product", "price", "quantity"}

        # Validate - should fail with empty dict
        is_valid, missing = preview.validate_variables(template.template_text, {})
        assert not is_valid
        assert len(missing) == 3

        # Validate - should succeed with all values
        values = {"product": "Widget", "price": "$29.99", "quantity": "5"}
        is_valid, missing = preview.validate_variables(template.template_text, values)
        assert is_valid
        assert missing == []

        # Fill template
        filled = preview.fill_template(template.template_text, values)
        assert filled == "Product: Widget\nPrice: $29.99\nQuantity: 5"

        # Preview with values
        success, message = preview.preview_template("workflow-test", values)
        assert success is True

    finally:
        templates.delete_template("workflow-test")


def test_variable_name_formats(preview):
    """Test different variable name formats."""
    # Underscore
    content = "Hello {{first_name}} {{last_name}}"
    variables = preview.extract_variables(content)
    assert variables == ["first_name", "last_name"]

    # Numbers
    content = "Item {{item1}} and {{item2}}"
    variables = preview.extract_variables(content)
    assert variables == ["item1", "item2"]

    # CamelCase
    content = "Hello {{firstName}} {{lastName}}"
    variables = preview.extract_variables(content)
    assert variables == ["firstName", "lastName"]


def test_fill_preserves_formatting(preview):
    """Test that filling preserves whitespace and formatting."""
    content = """
    Hello {{name}},

    Your appointment is at {{time}}.

    Thank you!
    """
    variables = {"name": "Bob", "time": "3:00 PM"}
    result = preview.fill_template(content, variables)
    assert "Hello Bob," in result
    assert "Your appointment is at 3:00 PM." in result
    # Should preserve line breaks
    assert result.count("\n") == content.count("\n")
