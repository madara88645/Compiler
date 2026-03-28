import json
import sys
from pathlib import Path
from unittest.mock import patch

from app.rag.parsers import (
    can_parse,
    get_supported_extensions,
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


def test_parse_pdf_success_pymupdf(tmp_path):
    """Test PDF parsing successfully using PyMuPDF (fitz)."""
    import sys
    from unittest.mock import MagicMock, patch
    from app.rag.parsers import parse_pdf

    mock_fitz = MagicMock()
    mock_doc = MagicMock()

    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "Hello, Page 1\n"
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "World, Page 2"

    # Iterator support for 'for page_num, page in enumerate(doc, 1)'
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
    import sys
    from unittest.mock import MagicMock, patch
    from app.rag.parsers import parse_pdf

    mock_pdfplumber = MagicMock()
    mock_pdf_context = MagicMock()
    mock_pdf_instance = MagicMock()

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Plumber Page 1"

    mock_pdf_instance.pages = [mock_page1]

    # Context manager support
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
    import sys
    from unittest.mock import patch
    from app.rag.parsers import parse_pdf

    with patch.dict(sys.modules, {"fitz": None, "pdfplumber": None}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "pdf"
        assert "No PDF parser available" in result.metadata.get("error", "")


def test_parse_pdf_exception(tmp_path):
    """Test PDF parsing behavior when an unexpected exception occurs."""
    import sys
    from unittest.mock import MagicMock, patch
    from app.rag.parsers import parse_pdf

    mock_fitz = MagicMock()
    mock_fitz.open.side_effect = ValueError("Corrupt PDF file")

    with patch.dict(sys.modules, {"fitz": mock_fitz}):
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        result = parse_pdf(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "pdf"
        assert "Corrupt PDF file" in result.metadata.get("error", "")
