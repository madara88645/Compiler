import json
import sys
from pathlib import Path
from unittest.mock import patch

from app.rag.parsers import (
    can_parse,
    get_supported_extensions,
    parse_plain_text,
    parse_yaml,
    parse_yaml_file,
    ParseResult,
)


def test_parse_plain_text_success(tmp_path):
    txt_content = "Hello world.\nThis is a test document."
    test_file = tmp_path / "test.txt"
    test_file.write_text(txt_content)

    result = parse_plain_text(test_file)

    assert isinstance(result, ParseResult)
    assert result.content == txt_content
    assert result.metadata["format"] == "plain_text"
    assert result.metadata["extension"] == ".txt"
    assert result.word_count == 7


def test_parse_plain_text_extension(tmp_path):
    py_content = "def hello():\n    print('world')"
    test_file = tmp_path / "test.py"
    test_file.write_text(py_content)

    result = parse_plain_text(test_file)

    assert isinstance(result, ParseResult)
    assert result.content == py_content
    assert result.metadata["format"] == "plain_text"
    assert result.metadata["extension"] == ".py"
    assert result.word_count == 3


def test_parse_plain_text_error(tmp_path):
    non_existent_path = tmp_path / "non_existent.txt"
    result = parse_plain_text(non_existent_path)

    assert isinstance(result, ParseResult)
    assert result.content == ""
    assert "error" in result.metadata
    assert (
        "No such file or directory" in result.metadata["error"]
        or "cannot find the file specified" in result.metadata["error"]
    )
    assert result.word_count == 0


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
