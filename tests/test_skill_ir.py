import pytest
from app.adapters.skill_ir import (
    SkillExportIR,
    _clean_section,
    _extract_sections,
    _extract_title,
    _normalise_type,
    _parse_dependencies,
    _parse_name_section,
    _parse_output_type,
    _parse_params,
    _to_snake,
    parse_skill_markdown,
)


@pytest.mark.parametrize(
    "input_str, expected",
    [
        # Simple string
        ("hello_world", "hello_world"),
        # Spaced strings
        ("hello world", "hello_world"),
        ("hello  world", "hello_world"),
        ("  hello world  ", "hello_world"),
        # CamelCase and PascalCase
        ("CamelCase", "camel_case"),
        ("PascalCase", "pascal_case"),
        ("camelCase", "camel_case"),
        # Consecutive uppercase (acronyms)
        ("HTTPResponse", "http_response"),
        ("parseXML", "parse_xml"),
        ("XMLParser", "xml_parser"),
        # kebab-case
        ("kebab-case", "kebab_case"),
        ("my-kebab-case-string", "my_kebab_case_string"),
        # Special characters
        ("hello! world?", "hello_world"),
        ("my@#$var", "my_var"),
        ("complex - variable - name", "complex_variable_name"),
        # Numbers
        ("var123", "var123"),
        ("var 123", "var_123"),
        ("Class1Method", "class1_method"),
        # Empty and nullish
        ("", "skill_name"),
        ("   ", "skill_name"),
        ("!@#$", "skill_name"),
    ],
)
def test_to_snake(input_str, expected):
    """Test converting various string formats to snake_case."""
    assert _to_snake(input_str) == expected


@pytest.mark.parametrize(
    "input_str, expected",
    [
        # Plain text
        ("hello world", "hello world"),
        ("  hello world  ", "hello world"),
        # Markdown fences
        ("```\nhello world\n```", "hello world"),
        ("```python\nhello world\n```", "hello world"),
        ("```\nline1\nline2\n```", "line1\nline2"),
        # Incomplete fences
        ("```\nhello world", "hello world"),
        ("```python\nhello world", "hello world"),
        # Empty fences
        ("```\n```", ""),
        ("```python\n```", ""),
        ("```", ""),
        ("```python", ""),
        # Extra whitespace around fences
        ("  ```\nhello world\n```  ", "hello world"),
        ("```\n  hello world  \n```", "hello world"),
    ],
)
def test_clean_section(input_str, expected):
    """Test removing markdown fences and whitespace."""
    assert _clean_section(input_str) == expected


def test_extract_sections():
    markdown = """
# Main Title
Intro text

## Name
My Skill

## Purpose
This skill does something.
It spans multiple lines.

## Empty Section

## Input Schema
| Name | Type |
|---|---|
| p1 | str |
"""
    sections = _extract_sections(markdown)
    assert sections.get("name") == "My Skill"
    assert sections.get("purpose") == "This skill does something.\nIt spans multiple lines."
    assert sections.get("empty section") == ""
    assert "Input Schema" not in sections
    assert "input schema" in sections


def test_extract_title():
    assert _extract_title("# My Awesome Skill") == "My Awesome Skill"
    assert _extract_title("# Some Skill Definition") == "Some Skill Definition"
    assert _extract_title("## Not a title\n# Real Title") == "Real Title"
    assert _extract_title("Just text") == "skill_name"
    assert _extract_title("# title - skill") == "title"
    assert _extract_title("# title - definition") == "title"


def test_parse_name_section():
    # _parse_name_section takes the first word, so "Some Name" -> "some", "Real Name" -> "real"
    assert _parse_name_section("Some Name") == "some"
    assert _parse_name_section("# ignored\nReal Name") == "real"
    assert _parse_name_section("") == ""


def test_parse_params_table():
    text = """
| Name | Type | Description | Required |
|---|---|---|---|
| user_id | integer | User ID | Yes |
| my_name | string | User name | No |
| - | - | - | - |
"""
    params = _parse_params(text)
    assert len(params) == 2

    assert params[0].name == "user_id"
    assert params[0].type == "int"
    assert params[0].description == "User ID"
    assert params[0].required is True

    assert params[1].name == "my_name"
    assert params[1].type == "str"
    assert params[1].description == "User name"
    assert params[1].required is False


def test_parse_params_bullet():
    text = """
- user_id (integer): User ID
* name (string): User name
- simple: Just a name
"""
    params = _parse_params(text)
    assert len(params) == 3

    assert params[0].name == "user_id"
    assert params[0].type == "int"
    assert params[0].description == "User ID"

    assert params[1].name == "name"
    assert params[1].type == "str"
    assert params[1].description == "User name"

    assert params[2].name == "simple"
    assert params[2].type == "str"


@pytest.mark.parametrize(
    "input_str, expected_type",
    [
        ("Returns a dict of values", "dict"),
        ("json object", "dict"),
        ("Array of strings", "list"),
        ("list of users", "list"),
        ("Returns a bool", "bool"),
        ("boolean flag", "bool"),
        ("int value", "int"),
        ("integer", "int"),
        ("number", "int"),
        ("float value", "float"),
        ("decimal", "float"),
        ("Just a string", "str"),
        ("", "str"),
    ],
)
def test_parse_output_type(input_str, expected_type):
    parsed_type, desc = _parse_output_type(input_str)
    assert parsed_type == expected_type
    assert desc == input_str


def test_parse_dependencies():
    text = """
- requests
* pydantic
Some text
- math
"""
    deps = _parse_dependencies(text)
    assert deps == ["requests", "pydantic", "math"]


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("string", "str"),
        ("text", "str"),
        ("integer", "int"),
        ("number", "int"),
        ("float", "float"),
        ("double", "float"),
        ("boolean", "bool"),
        ("bool", "bool"),
        ("list", "list"),
        ("array", "list"),
        ("dict", "dict"),
        ("object", "dict"),
        ("json", "dict"),
        ("any", "Any"),
        ("custom_type", "custom_type"),
        ("  STRING  ", "str"),
    ],
)
def test_normalise_type(input_str, expected):
    assert _normalise_type(input_str) == expected


def test_parse_skill_markdown():
    markdown = """
# The Best Skill

## Name
Best Skill

## Purpose
Does the best things.
```
code block inside purpose shouldn't break things
```

## Input Schema
- param1 (string): First param

## Output Schema
Returns a boolean indicating success.

## Dependencies
- requests
"""
    result = parse_skill_markdown(markdown)
    assert isinstance(result, SkillExportIR)
    # _parse_name_section takes the first word, so "Best Skill" -> "best"
    assert result.name == "best"
    assert "Does the best things" in result.purpose
    assert len(result.params) == 1
    assert result.params[0].name == "param1"
    assert result.output_type == "bool"
    assert "Returns a boolean" in result.output_description
    assert result.dependencies == ["requests"]
    assert result.raw_definition == markdown.strip()


def test_parse_skill_markdown_fallback_name():
    markdown = """
# Fallback Title

## Purpose
No name section
"""
    result = parse_skill_markdown(markdown)
    assert result.name == "fallback_title"
