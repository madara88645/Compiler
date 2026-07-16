"""CLI integration tests for RAG subcommands.

Covers: index, query, stats, prune — each using a temporary SQLite database
to avoid side-effects on the default DB.

Fixes #1074.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def _index_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create sample text files and return (directory, db_path)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Hello World\nThis is a readme file.", encoding="utf-8")
    (docs / "notes.txt").write_text("Meeting notes from the design review.", encoding="utf-8")
    db = tmp_path / "test_rag.db"
    return docs, db


def test_rag_index_success(tmp_path: Path):
    """Indexing a directory with text files should succeed."""
    docs, db = _index_fixture(tmp_path)

    result = runner.invoke(
        app,
        ["rag", "index", str(docs), "--db-path", str(db), "--ext", ".md", "--ext", ".txt"],
    )

    assert result.exit_code == 0, result.output
    assert "indexed" in result.output.lower() or "docs=" in result.output
    assert db.exists()


def test_rag_query_after_index(tmp_path: Path):
    """Querying the index should return results."""
    docs, db = _index_fixture(tmp_path)

    # First, index
    idx_result = runner.invoke(
        app,
        ["rag", "index", str(docs), "--db-path", str(db), "--ext", ".md", "--ext", ".txt"],
    )
    assert idx_result.exit_code == 0, idx_result.output

    # Then query
    result = runner.invoke(
        app,
        ["rag", "query", "readme", "--db-path", str(db), "--k", "2", "--json"],
    )

    assert result.exit_code == 0, result.output


def test_rag_stats(tmp_path: Path):
    """stats should report chunk/document counts."""
    docs, db = _index_fixture(tmp_path)

    # Index first
    runner.invoke(
        app,
        ["rag", "index", str(docs), "--db-path", str(db), "--ext", ".md", "--ext", ".txt"],
    )

    result = runner.invoke(app, ["rag", "stats", "--db-path", str(db)])

    assert result.exit_code == 0, result.output


def test_rag_prune(tmp_path: Path):
    """prune should complete without error on an indexed DB."""
    docs, db = _index_fixture(tmp_path)

    runner.invoke(
        app,
        ["rag", "index", str(docs), "--db-path", str(db), "--ext", ".md", "--ext", ".txt"],
    )

    result = runner.invoke(app, ["rag", "prune", "--db-path", str(db)])

    assert result.exit_code == 0, result.output


def test_rag_index_empty_dir(tmp_path: Path):
    """Indexing an empty directory should succeed with zero docs."""
    empty = tmp_path / "empty"
    empty.mkdir()
    db = tmp_path / "empty.db"

    result = runner.invoke(
        app,
        ["rag", "index", str(empty), "--db-path", str(db)],
    )

    assert result.exit_code == 0, result.output
    assert "docs=0" in result.output
