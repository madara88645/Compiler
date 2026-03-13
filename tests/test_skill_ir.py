import pytest
from app.adapters.skill_ir import _to_snake

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
    ]
)
def test_to_snake(input_str, expected):
    """Test converting various string formats to snake_case."""
    assert _to_snake(input_str) == expected
