"""tests/test_rag_parsers_gap.py — direct unit tests for app.rag.parsers functions
that had no dedicated test coverage: parse_json, parse_docx, register_parser.
"""

import sys
from unittest.mock import MagicMock, patch

from app.rag.parsers import (
    ParseResult,
    PARSERS,
    can_parse,
    get_supported_extensions,
    parse_json,
    parse_docx,
    register_parser,
)


# --- parse_json ---


def test_parse_json_success_pretty_prints(tmp_path):
    test_file = tmp_path / "test.json"
    test_file.write_text('{"b": 2, "a": 1}')

    result = parse_json(test_file)

    assert isinstance(result, ParseResult)
    assert result.content == '{\n  "b": 2,\n  "a": 1\n}'
    assert result.metadata["format"] == "json"
    assert result.metadata["extension"] == ".json"
    assert result.word_count == len(result.content.split())


def test_parse_json_unicode_is_not_escaped(tmp_path):
    test_file = tmp_path / "unicode.json"
    test_file.write_text('{"name": "Çağla"}', encoding="utf-8")

    result = parse_json(test_file)

    assert "Çağla" in result.content
    assert "\\u" not in result.content


def test_parse_json_invalid_json_returns_error(tmp_path):
    test_file = tmp_path / "bad.json"
    test_file.write_text("{not valid json")

    result = parse_json(test_file)

    assert result.content == ""
    assert "error" in result.metadata


def test_parse_json_file_not_found():
    from pathlib import Path

    result = parse_json(Path("/nonexistent/path/does-not-exist.json"))
    assert result.content == ""
    assert "error" in result.metadata


def test_parse_json_empty_object(tmp_path):
    test_file = tmp_path / "empty.json"
    test_file.write_text("{}")

    result = parse_json(test_file)

    assert result.content == "{}"
    assert result.metadata["format"] == "json"


# --- parse_docx ---


def _make_mock_docx_module(paragraphs, tables):
    """Build a fake `docx` module whose Document(path) returns an object
    with .paragraphs (list of objects with .text) and .tables (list of
    objects with .rows -> list of objects with .cells -> list of objects
    with .text), mirroring python-docx's real API surface.
    """
    mock_doc_instance = MagicMock()
    mock_doc_instance.paragraphs = [MagicMock(text=p) for p in paragraphs]

    mock_tables = []
    for table_rows in tables:
        mock_table = MagicMock()
        mock_rows = []
        for row_cells in table_rows:
            mock_row = MagicMock()
            mock_row.cells = [MagicMock(text=c) for c in row_cells]
            mock_rows.append(mock_row)
        mock_table.rows = mock_rows
        mock_tables.append(mock_table)
    mock_doc_instance.tables = mock_tables

    mock_docx_module = MagicMock()
    mock_docx_module.Document.return_value = mock_doc_instance
    return mock_docx_module


def test_parse_docx_success_paragraphs_and_tables(tmp_path):
    mock_docx = _make_mock_docx_module(
        paragraphs=["Hello world", "", "Second paragraph"],
        tables=[[["A", "B"], ["1", "2"]]],
    )

    with patch.dict(sys.modules, {"docx": mock_docx}):
        test_file = tmp_path / "test.docx"
        test_file.touch()

        result = parse_docx(test_file)

        assert "Hello world" in result.content
        assert "Second paragraph" in result.content
        assert "[Table]" in result.content
        assert "A | B" in result.content
        assert "1 | 2" in result.content
        assert result.metadata["format"] == "docx"
        assert result.metadata["extension"] == ".docx"
        assert result.metadata["paragraph_count"] == 2  # empty paragraph excluded
        assert result.metadata["table_count"] == 1
        assert result.metadata["parser"] == "python-docx"
        assert result.word_count == len(result.content.split())


def test_parse_docx_empty_document(tmp_path):
    mock_docx = _make_mock_docx_module(paragraphs=[], tables=[])

    with patch.dict(sys.modules, {"docx": mock_docx}):
        test_file = tmp_path / "empty.docx"
        test_file.touch()

        result = parse_docx(test_file)

        assert result.content == ""
        assert result.metadata["paragraph_count"] == 0
        assert result.metadata["table_count"] == 0


def test_parse_docx_import_error(tmp_path):
    with patch.dict(sys.modules, {"docx": None}):
        test_file = tmp_path / "test.docx"
        test_file.touch()

        result = parse_docx(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "docx"
        assert "python-docx not installed" in result.metadata["error"]


def test_parse_docx_unexpected_exception(tmp_path):
    mock_docx = MagicMock()
    mock_docx.Document.side_effect = ValueError("corrupt docx")

    with patch.dict(sys.modules, {"docx": mock_docx}):
        test_file = tmp_path / "test.docx"
        test_file.touch()

        result = parse_docx(test_file)

        assert result.content == ""
        assert result.metadata["format"] == "docx"
        assert "An internal error occurred during parsing." in result.metadata["error"]


# --- register_parser ---


def test_register_parser_adds_new_extension():
    original_parsers = dict(PARSERS)
    try:
        custom_parser = MagicMock(return_value=ParseResult(content="custom"))
        register_parser(".customext", custom_parser)

        assert ".customext" in get_supported_extensions()
        assert can_parse(__import__("pathlib").Path("file.customext")) is True
        assert PARSERS[".customext"] is custom_parser
    finally:
        PARSERS.clear()
        PARSERS.update(original_parsers)


def test_register_parser_normalizes_extension_case():
    original_parsers = dict(PARSERS)
    try:
        custom_parser = MagicMock()
        register_parser(".UPPER", custom_parser)

        assert ".upper" in PARSERS
        assert ".UPPER" not in PARSERS
    finally:
        PARSERS.clear()
        PARSERS.update(original_parsers)


def test_register_parser_overrides_existing_extension(tmp_path):
    original_parsers = dict(PARSERS)
    try:
        override_parser = MagicMock(return_value=ParseResult(content="overridden"))
        register_parser(".txt", override_parser)

        from app.rag.parsers import parse_file

        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        result = parse_file(test_file)

        assert result.content == "overridden"
        override_parser.assert_called_once_with(test_file)
    finally:
        PARSERS.clear()
        PARSERS.update(original_parsers)
