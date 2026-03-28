import json
import sys
from pathlib import Path
from unittest.mock import patch

from app.rag.parsers import (
    can_parse,
    get_supported_extensions,
    parse_yaml,
    parse_yaml_file,
    parse_file,
    ParseResult,
)


def test_parse_yaml_str_success():
    yaml_str = "key: value\nnumber: 42"
    result = parse_yaml(yaml_str)

    parsed = json.loads(result)
    assert parsed["key"] == "value"
    assert parsed["number"] == 42


def test_parse_yaml_bytes_success():
    yaml_bytes = b"key: value\nnumber: 42"
    result = parse_yaml(yaml_bytes)

    parsed = json.loads(result)
    assert parsed["key"] == "value"
    assert parsed["number"] == 42


def test_parse_yaml_invalid_yaml():
    yaml_str = "key: [unclosed list"
    result = parse_yaml(yaml_str)
    # Should fall back to returning the original content
    assert result == yaml_str


def test_parse_yaml_import_error():
    yaml_str = "key: value\nnumber: 42"
    # Simulate ImportError for 'yaml'
    with patch.dict(sys.modules, {"yaml": None}):
        result = parse_yaml(yaml_str)
        # Should fall back to returning the original plain text content
        assert result == yaml_str


def test_parse_yaml_file_success(tmp_path):
    yaml_content = "key: value\nnumber: 42\n"
    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    result = parse_yaml_file(test_file)

    assert isinstance(result, ParseResult)
    parsed = json.loads(result.content)
    assert parsed["key"] == "value"
    assert parsed["number"] == 42
    assert result.metadata["format"] == "yaml"
    assert result.metadata["extension"] == ".yaml"


def test_parse_yaml_file_error(tmp_path):
    non_existent_path = tmp_path / "non_existent.yaml"
    result = parse_yaml_file(non_existent_path)

    assert result.content == ""
    assert "error" in result.metadata


def test_get_supported_extensions():
    """Test get_supported_extensions returns a list of extensions containing expected values."""
    extensions = get_supported_extensions()

    # Check that it returns a list
    assert isinstance(extensions, list)

    # Check that it has expected standard extensions
    assert ".txt" in extensions
    assert ".py" in extensions
    assert ".md" in extensions
    assert ".pdf" in extensions
    assert ".docx" in extensions

    # Check extensions are all strings starting with a dot
    for ext in extensions:
        assert isinstance(ext, str)
        assert ext.startswith(".")


def test_can_parse():
    """Test can_parse logic for supported and unsupported extensions."""
    # Create temp paths without needing them to exist on disk
    assert can_parse(Path("test.py")) is True
    assert can_parse(Path("test.txt")) is True
    assert can_parse(Path("test.md")) is True
    assert can_parse(Path("test.pdf")) is True
    assert can_parse(Path("test.docx")) is True
    assert can_parse(Path("test.unknown_extension")) is False
    assert can_parse(Path("no_extension")) is False


def test_parse_file_not_exists(tmp_path):
    non_existent_path = tmp_path / "does_not_exist.txt"
    result = parse_file(non_existent_path)
    assert result.content == ""
    assert "error" in result.metadata
    assert "File not found" in result.metadata["error"]


def test_parse_file_registered_parser(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, world!")
    result = parse_file(test_file)
    assert result.content == "Hello, world!"
    assert result.metadata["format"] == "plain_text"
    assert result.metadata["extension"] == ".txt"


def test_parse_file_unknown_fallback_true(tmp_path):
    test_file = tmp_path / "test.unknown_extension"
    test_file.write_text("Hello, world!")
    result = parse_file(test_file, fallback_to_text=True)
    assert result.content == "Hello, world!"
    assert result.metadata["format"] == "plain_text"
    assert result.metadata["extension"] == ".unknown_extension"


def test_parse_file_unknown_fallback_false(tmp_path):
    test_file = tmp_path / "test.unknown_extension"
    test_file.write_text("Hello, world!")
    result = parse_file(test_file, fallback_to_text=False)
    assert result.content == ""
    assert "error" in result.metadata
    assert "No parser registered" in result.metadata["error"]


def test_parse_file_fallback_exception(tmp_path):
    test_file = tmp_path / "test.unknown_extension"
    test_file.write_text("Hello, world!")

    # We mock parse_plain_text to raise an exception
    with patch("app.rag.parsers.parse_plain_text", side_effect=Exception("Mocked error")):
        result = parse_file(test_file, fallback_to_text=True)
        assert result.content == ""
        assert "error" in result.metadata
        assert "Unable to parse file" in result.metadata["error"]
