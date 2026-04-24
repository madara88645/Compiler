import json
import sys
from pathlib import Path
from unittest.mock import patch

from unittest.mock import MagicMock

from app.rag.parsers import (
    can_parse,
    get_supported_extensions,
    parse_file,
    parse_html,
    parse_markdown,
    parse_pdf,
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


def test_parse_yaml_import_error_bytes():
    yaml_bytes = b"key: value\nnumber: 42"
    # Simulate ImportError for 'yaml' with bytes content
    with patch.dict(sys.modules, {"yaml": None}):
        result = parse_yaml(yaml_bytes)
        # Should decode the bytes and fall back to returning the original plain text content
        assert result == "key: value\nnumber: 42"


def test_parse_yaml_empty_string():
    # Empty string should return empty string since parsed will be None
    result = parse_yaml("")
    assert result == ""


def test_parse_yaml_empty_bytes():
    # Empty bytes should return empty string since parsed will be None
    result = parse_yaml(b"")
    assert result == ""


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


# --- parse_file tests (from PR #261) ---


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

    with patch("app.rag.parsers.parse_plain_text", side_effect=Exception("Mocked error")):
        result = parse_file(test_file, fallback_to_text=True)
        assert result.content == ""
        assert "error" in result.metadata
        assert "Unable to parse file" in result.metadata["error"]


# --- parse_html tests (from PR #263) ---


def test_parse_html_success(tmp_path):
    html_content = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Heading 1</h1>
            <p>This is a <b>paragraph</b> with <a href="https://example.com">a link</a>.</p>
        </body>
    </html>
    """
    test_file = tmp_path / "test.html"
    test_file.write_text(html_content)

    result = parse_html(test_file)
    assert isinstance(result, ParseResult)
    assert result.content == "Test Page Heading 1 This is a paragraph with a link ."
    assert result.metadata["format"] == "html"
    assert result.metadata["extension"] == ".html"


def test_parse_html_remove_scripts_and_styles(tmp_path):
    html_content = """
    <html>
        <head>
            <style type="text/css">
                body { color: red; }
            </style>
            <script>
                console.log("Hello, World!");
            </script>
        </head>
        <body>
            <p>Visible content</p>
        </body>
    </html>
    """
    test_file = tmp_path / "test.html"
    test_file.write_text(html_content)

    result = parse_html(test_file)
    assert "console.log" not in result.content
    assert "body { color: red; }" not in result.content
    assert result.content == "Visible content"


def test_parse_html_decode_entities(tmp_path):
    html_content = """
    <p>Entity test: &lt; &gt; &amp; &quot; &nbsp;</p>
    """
    test_file = tmp_path / "test.html"
    test_file.write_text(html_content)

    result = parse_html(test_file)
    assert result.content == 'Entity test: < > & "'


def test_parse_html_error(tmp_path):
    non_existent_path = tmp_path / "non_existent.html"
    result = parse_html(non_existent_path)

    assert result.content == ""
    assert "error" in result.metadata


# --- parse_pdf tests (from PR #265) ---


def test_parse_pdf_success_pymupdf(tmp_path):
    """Test PDF parsing successfully using PyMuPDF (fitz)."""
    mock_fitz = MagicMock()
    mock_doc = MagicMock()

    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "Hello, Page 1\n"
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "World, Page 2"

    mock_doc.__iter__.return_value = iter([mock_page1, mock_page2])
    mock_doc.__len__.return_value = 2

    mock_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert "Hello, Page 1" in result.content
        assert "World, Page 2" in result.content
        assert "[Page 1]" in result.content
        assert "[Page 2]" in result.content

        assert result.metadata["format"] == "pdf"
        assert result.metadata["extension"] == ".pdf"
        assert result.metadata["parser"] == "pymupdf"
        assert result.metadata["page_count"] == 2
        assert result.metadata["pages_with_text"] == 2


def test_parse_pdf_success_pdfplumber(tmp_path):
    """Test PDF parsing falling back to pdfplumber when fitz fails to import."""
    mock_pdfplumber = MagicMock()
    mock_pdf_context = MagicMock()
    mock_pdf_instance = MagicMock()

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Plumber Page 1"

    mock_pdf_instance.pages = [mock_page1]

    mock_pdf_context.__enter__.return_value = mock_pdf_instance
    mock_pdfplumber.open.return_value = mock_pdf_context

    with patch.dict(sys.modules, {"fitz": None, "pdfplumber": mock_pdfplumber}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert "Plumber Page 1" in result.content
        assert "[Page 1]" in result.content

        assert result.metadata["format"] == "pdf"
        assert result.metadata["extension"] == ".pdf"
        assert result.metadata["parser"] == "pdfplumber"
        assert result.metadata["page_count"] == 1
        assert result.metadata["pages_with_text"] == 1


def test_parse_pdf_no_parsers(tmp_path):
    """Test PDF parsing behavior when neither fitz nor pdfplumber are available."""
    with patch.dict(sys.modules, {"fitz": None, "pdfplumber": None}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "pdf"
        assert "An internal error occurred during parsing." in result.metadata.get(
            "error", ""
        ) or "No PDF parser available" in result.metadata.get("error", "")


def test_parse_pdf_exception(tmp_path):
    """Test PDF parsing behavior when an unexpected exception occurs."""
    mock_fitz = MagicMock()
    mock_fitz.open.side_effect = ValueError("Corrupt PDF file")

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "pdf"
        assert "An internal error occurred during parsing." in result.metadata.get(
            "error", ""
        ) or "No PDF parser available" in result.metadata.get("error", "")
