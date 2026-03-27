import json
import sys
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock

from app.rag.parsers import (
    can_parse,
    get_supported_extensions,
    parse_json,
    parse_markdown,
    parse_yaml,
    parse_yaml_file,
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


def test_parse_json_file_not_found(tmp_path):
    non_existent_path = tmp_path / "non_existent.json"
    result = parse_json(non_existent_path)

    assert result.content == ""
    assert "error" in result.metadata


def test_parse_json_success(tmp_path):
    json_content = '{"key": "value", "number": 42}'
    test_file = tmp_path / "test.json"
    test_file.write_text(json_content)

    result = parse_json(test_file)

    assert isinstance(result, ParseResult)
    parsed = json.loads(result.content)
    assert parsed["key"] == "value"
    assert parsed["number"] == 42
    assert result.metadata["format"] == "json"
    assert result.metadata["extension"] == ".json"
    assert result.word_count == len(result.content.split())


def test_parse_json_invalid_format(tmp_path):
    invalid_json = '{"key": "value", "number": 42'  # Missing closing brace
    test_file = tmp_path / "test_invalid.json"
    test_file.write_text(invalid_json)

    result = parse_json(test_file)

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


def test_parse_markdown_success(tmp_path):
    md_content = """# Main Title

Some introductory text.

## Section 1
More text here.
```python
print("Hello World")
```

### Subsection
Even more text.
```bash
echo "Hello"
```
"""
    test_file = tmp_path / "test.md"
    test_file.write_text(md_content)

    result = parse_markdown(test_file)

    assert isinstance(result, ParseResult)
    assert result.content == md_content
    assert result.word_count == len(md_content.split())
    assert result.metadata["format"] == "markdown"
    assert result.metadata["extension"] == ".md"
    assert result.metadata["header_count"] == 3
    assert set(result.metadata["code_languages"]) == {"python", "bash"}
    assert result.metadata["has_code"] is True

    assert len(result.sections) == 3
    assert result.sections[0]["level"] == 1
    assert result.sections[0]["title"] == "Main Title"
    assert result.sections[0]["line"] == 1

    assert result.sections[1]["level"] == 2
    assert result.sections[1]["title"] == "Section 1"
    assert result.sections[1]["line"] == 5

    assert result.sections[2]["level"] == 3
    assert result.sections[2]["title"] == "Subsection"
    assert result.sections[2]["line"] == 11


def test_parse_markdown_empty(tmp_path):
    test_file = tmp_path / "empty.md"
    test_file.write_text("")

    result = parse_markdown(test_file)

    assert result.content == ""
    assert result.word_count == 0
    assert result.metadata["header_count"] == 0
    assert result.metadata["code_languages"] == []
    assert result.metadata["has_code"] is False
    assert len(result.sections) == 0


def test_parse_markdown_no_headers_no_code(tmp_path):
    md_content = "Just some plain text.\nWith another line."
    test_file = tmp_path / "plain.md"
    test_file.write_text(md_content)

    result = parse_markdown(test_file)

    assert result.content == md_content
    assert result.metadata["header_count"] == 0
    assert result.metadata["code_languages"] == []
    assert result.metadata["has_code"] is False
    assert len(result.sections) == 0


def test_parse_markdown_unclosed_code_block(tmp_path):
    md_content = """# Header
```python
def foo():
    pass
"""
    test_file = tmp_path / "unclosed.md"
    test_file.write_text(md_content)

    result = parse_markdown(test_file)

    assert result.metadata["header_count"] == 1
    assert result.metadata["code_languages"] == []
    assert result.metadata["has_code"] is False


def test_parse_markdown_code_block_ignores_headers(tmp_path):
    md_content = """# Real Header
```python
# Not A Header
```
"""
    test_file = tmp_path / "ignores.md"
    test_file.write_text(md_content)

    result = parse_markdown(test_file)

    assert result.metadata["header_count"] == 1
    assert result.sections[0]["title"] == "Real Header"


def test_parse_markdown_error(tmp_path):
    non_existent_path = tmp_path / "non_existent.md"
    result = parse_markdown(non_existent_path)

    assert result.content == ""
    assert "error" in result.metadata


def test_parse_pdf_fitz_success(tmp_path):
    from app.rag.parsers import parse_pdf

    # Create a dummy file
    test_pdf = tmp_path / "test.pdf"
    test_pdf.touch()

    # Mock fitz (PyMuPDF)
    mock_fitz = MagicMock()
    mock_doc = MagicMock()

    # Mock 2 pages
    mock_page_1 = MagicMock()
    mock_page_1.get_text.return_value = "Page 1 content."
    mock_page_2 = MagicMock()
    mock_page_2.get_text.return_value = "Page 2 content."

    # Set up len(doc)
    mock_doc.__len__.return_value = 2
    # Set up iteration over doc
    mock_doc.__iter__.return_value = iter([mock_page_1, mock_page_2])

    mock_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        result = parse_pdf(test_pdf)

    assert "Page 1 content." in result.content
    assert "Page 2 content." in result.content
    assert result.page_count == 2
    assert result.metadata["format"] == "pdf"
    assert result.metadata["parser"] == "pymupdf"
    assert result.metadata["page_count"] == 2
    assert result.metadata["pages_with_text"] == 2
    mock_fitz.open.assert_called_once_with(str(test_pdf))
    mock_doc.close.assert_called_once()


def test_parse_pdf_pdfplumber_success(tmp_path):
    from app.rag.parsers import parse_pdf

    test_pdf = tmp_path / "test.pdf"
    test_pdf.touch()

    # Mock pdfplumber
    mock_pdfplumber = MagicMock()
    mock_pdf = MagicMock()

    # Mock pages
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Plumber page content."
    mock_pdf.pages = [mock_page]

    # Set up context manager
    mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

    # Patch fitz to raise ImportError, and patch pdfplumber
    with patch.dict(sys.modules, {"fitz": None, "pdfplumber": mock_pdfplumber}):
        result = parse_pdf(test_pdf)

    assert "Plumber page content." in result.content
    assert result.page_count == 1
    assert result.metadata["format"] == "pdf"
    assert result.metadata["parser"] == "pdfplumber"
    mock_pdfplumber.open.assert_called_once_with(str(test_pdf))


def test_parse_pdf_no_parsers(tmp_path):
    from app.rag.parsers import parse_pdf

    test_pdf = tmp_path / "test.pdf"
    test_pdf.touch()

    with patch.dict(sys.modules, {"fitz": None, "pdfplumber": None}):
        result = parse_pdf(test_pdf)

    assert result.content == ""
    assert "No PDF parser available" in result.metadata["error"]


def test_parse_pdf_exception_handling(tmp_path):
    from app.rag.parsers import parse_pdf

    test_pdf = tmp_path / "test.pdf"
    test_pdf.touch()

    mock_fitz = MagicMock()
    mock_fitz.open.side_effect = Exception("Corrupt PDF file")

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        result = parse_pdf(test_pdf)

    assert result.content == ""
    assert result.metadata["error"] == "Corrupt PDF file"
