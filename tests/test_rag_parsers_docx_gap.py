"""Coverage gap: app.rag.parsers.parse_docx (previously untested).

Builds a real .docx fixture via python-docx (Document with a paragraph and a
table), then exercises the success path plus the ImportError and generic
exception fallback branches.
"""
import sys
from unittest.mock import patch

import pytest

from app.rag.parsers import parse_docx, ParseResult

docx = pytest.importorskip("docx", reason="python-docx not installed")


def _build_sample_docx(tmp_path):
    document = docx.Document()
    document.add_paragraph("Hello from a real docx paragraph.")

    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Name"
    table.rows[0].cells[1].text = "Score"
    table.rows[1].cells[0].text = "Alice"
    table.rows[1].cells[1].text = "42"

    docx_path = tmp_path / "sample.docx"
    document.save(str(docx_path))
    return docx_path


def test_parse_docx_success(tmp_path):
    docx_path = _build_sample_docx(tmp_path)

    result = parse_docx(docx_path)

    assert isinstance(result, ParseResult)
    assert "Hello from a real docx paragraph." in result.content
    assert "[Table]" in result.content
    assert "Name | Score" in result.content
    assert "Alice | 42" in result.content

    assert result.metadata["format"] == "docx"
    assert result.metadata["extension"] == ".docx"
    assert result.metadata["parser"] == "python-docx"
    assert result.metadata["paragraph_count"] == 1
    assert result.metadata["table_count"] == 1

    assert result.word_count == len(result.content.split())
    assert result.word_count > 0


def test_parse_docx_empty_paragraphs_and_no_tables(tmp_path):
    document = docx.Document()
    document.add_paragraph("   ")  # whitespace-only paragraph should be skipped
    document.add_paragraph("Real content here")

    docx_path = tmp_path / "sparse.docx"
    document.save(str(docx_path))

    result = parse_docx(docx_path)

    assert result.content == "Real content here"
    assert result.metadata["paragraph_count"] == 1
    assert result.metadata["table_count"] == 0


def test_parse_docx_import_error(tmp_path):
    docx_path = _build_sample_docx(tmp_path)

    with patch.dict(sys.modules, {"docx": None}):
        result = parse_docx(docx_path)

    assert result.content == ""
    assert result.metadata["format"] == "docx"
    assert "python-docx not installed" in result.metadata["error"]


def test_parse_docx_generic_exception(tmp_path):
    non_existent_path = tmp_path / "does_not_exist.docx"

    result = parse_docx(non_existent_path)

    assert result.content == ""
    assert result.metadata["format"] == "docx"
    assert "An internal error occurred during parsing." in result.metadata["error"]
