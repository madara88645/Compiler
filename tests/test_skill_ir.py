import pytest
from app.adapters.skill_ir import (
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
Intro text here
## Name
test_skill
## Purpose
To do something
## Input Schema
| Name |
## Output Schema
returns dict
"""
    sections = _extract_sections(markdown)
    assert sections.get("name") == "test_skill"
    assert sections.get("purpose") == "To do something"
    assert sections.get("input schema") == "| Name |"
    assert sections.get("output schema") == "returns dict"


def test_extract_sections_no_sections():
    markdown = "Just some text without sections"
    assert _extract_sections(markdown) == {}


@pytest.mark.parametrize(
    "input_md, expected",
    [
        ("# My Skill Definition", "My Skill Definition"),
        ("# Another Skill - Definition", "Another Skill"),
        ("# Just A Title", "Just A Title"),
        ("## Not A Main Title", "skill_name"),
        ("# skill definition", "skill definition"),
    ],
)
def test_extract_title(input_md, expected):
    assert _extract_title(input_md) == expected


def test_parse_name_section():
    assert _parse_name_section("my_skill_name\n# something") == "my_skill_name"
    assert _parse_name_section("\n   camelCaseSkill   \n") == "camel_case_skill"
    assert _parse_name_section("") == ""
    assert _parse_name_section("# Title\nmy_skill") == "my_skill"


def test_parse_params_table():
    md = """
| Name | Type | Description | Required |
|---|---|---|---|
| param1 | string | A string | Yes |
| param2 | int | An int | No |
| name | string | should skip | yes |
    """
    params = _parse_params(md)
    assert len(params) == 2
    assert params[0].name == "param1"
    assert params[0].type == "str"
    assert params[0].required is True
    assert params[1].name == "param2"
    assert params[1].type == "int"
    assert params[1].required is False


def test_parse_params_bullet():
    md = """
- param1 (string): A string
* param2 (int): An int
- plain_param
    """
    params = _parse_params(md)
    assert len(params) == 3
    assert params[0].name == "param1"
    assert params[0].type == "str"
    assert params[1].name == "param2"
    assert params[1].type == "int"
    assert params[2].name == "plain_param"
    assert params[2].type == "str"


@pytest.mark.parametrize(
    "input_md, expected_type",
    [
        ("Returns a json object", "dict"),
        ("List of strings", "list"),
        ("A boolean value", "bool"),
        ("Returns an integer", "int"),
        ("Float value", "float"),
        ("Just a string", "str"),
    ],
)
def test_parse_output_type(input_md, expected_type):
    typ, desc = _parse_output_type(input_md)
    assert typ == expected_type
    assert desc == input_md


def test_parse_dependencies():
    md = """
- reqs
* other_dep
    """
    deps = _parse_dependencies(md)
    assert deps == ["reqs", "other_dep"]
    assert _parse_dependencies("none") == []


@pytest.mark.parametrize(
    "input_type, expected",
    [
        ("string", "str"),
        ("number", "int"),
        ("double", "float"),
        ("json", "dict"),
        ("array", "list"),
        ("unknown", "unknown"),
    ],
)
def test_normalise_type(input_type, expected):
    assert _normalise_type(input_type) == expected


def test_parse_skill_markdown():
    md = """
# Awesome Skill Definition

## Name
awesome_skill

## Purpose
Does awesome things

## Input Schema
- text (string): text to process

## Output Schema
returns a JSON object

## Dependencies
- requests
    """
    ir = parse_skill_markdown(md)
    assert ir.name == "awesome_skill"
    assert ir.purpose == "Does awesome things"
    assert len(ir.params) == 1
    assert ir.params[0].name == "text"
    assert ir.output_type == "dict"
    assert ir.dependencies == ["requests"]


def test_parse_skill_markdown_fallback_title():
    md = """
# Awesome Skill Definition

## Purpose
Does awesome things
    """
    ir = parse_skill_markdown(md)
    assert ir.name == "awesome_skill_definition"
    assert ir.purpose == "Does awesome things"
