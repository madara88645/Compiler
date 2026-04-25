"""Test the stabilized /rag upload/search endpoints."""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.rag import simple_index


@pytest.fixture
def rag_test_env(monkeypatch):
    """Create an isolated temp env for RAG API tests."""
    td = tempfile.mkdtemp()
    original_cwd = Path.cwd()
    test_db = os.path.join(td, "test_upload.db")
    upload_dir = os.path.join(td, "uploads")

    try:
        with patch("app.rag.simple_index.DEFAULT_DB_PATH", test_db):
            monkeypatch.setenv("PROMPTC_UPLOAD_DIR", upload_dir)
            monkeypatch.setenv("PROMPTC_RAG_ALLOWED_ROOTS", td)
            os.chdir(td)
            yield {"temp_dir": td, "test_db": test_db, "upload_dir": upload_dir}
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(td, ignore_errors=True)


@pytest.fixture
def client(rag_test_env):
    """Create a test client, patching startup to skip HybridCompiler."""
    del rag_test_env
    from api.main import app

    with TestClient(app) as c:
        yield c


def test_rag_upload_indexes_file(client):
    """Uploading a file should index it and return chunk count."""
    response = client.post(
        "/rag/upload",
        json={
            "filename": "auth.py",
            "content": "def login(username, password):\n    if username == 'admin':\n        return True\n    return False",
            "force": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ingested_docs"] == 1
    assert data["total_chunks"] >= 1
    assert data["filename"] == "auth.py"
    assert data["success"] is True
    assert data["num_chunks"] == data["total_chunks"]
    assert "auth.py" in data["message"]


def test_rag_stats_get(client):
    """GET /rag/stats should return index statistics."""
    response = client.get("/rag/stats")
    assert response.status_code == 200
    data = response.json()
    assert "docs" in data
    assert "chunks" in data


def test_rag_upload_then_search(client):
    """Upload a file, then search for its content."""
    # Upload
    client.post(
        "/rag/upload",
        json={
            "filename": "calculator.py",
            "content": "def add(a, b):\n    return a + b\n\ndef multiply(x, y):\n    return x * y",
            "force": True,
        },
    )

    # Search
    response = client.post("/rag/search", json={"query": "multiply", "limit": 3})

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    found = any("multiply" in r["snippet"].lower() for r in results)
    assert found, f"Expected 'multiply' in results: {results}"
    assert all(set(result.keys()) == {"path", "snippet", "score"} for result in results)


def test_rag_upload_indexes_unique_content_for_search(client):
    """Uploaded content should become searchable, not just return a stub success payload."""
    unique_term = "neuroflux_unique_signal_4271"

    upload = client.post(
        "/rag/upload",
        json={
            "filename": "notes.md",
            "content": f"Project notes: keep track of {unique_term} in the context index.",
            "force": True,
        },
    )

    assert upload.status_code == 200
    upload_data = upload.json()
    assert upload_data["success"] is True

    search = client.post(
        "/rag/search", json={"query": unique_term, "limit": 3, "method": "keyword"}
    )

    assert search.status_code == 200
    results = search.json()
    found = any(unique_term in str(r) for r in results)
    assert found, f"Expected uploaded term in results: {results}"


def test_rag_upload_preserves_relative_paths_for_duplicate_filenames(client):
    """Folder uploads should not collapse files that share the same basename."""
    first = client.post(
        "/rag/upload",
        json={
            "filename": "index.ts",
            "relative_path": "src/components/index.ts",
            "content": "export const headerMarker = 'header_unique_signal';",
            "force": True,
        },
    )
    second = client.post(
        "/rag/upload",
        json={
            "filename": "index.ts",
            "relative_path": "src/pages/index.ts",
            "content": "export const pageMarker = 'page_unique_signal';",
            "force": True,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    stats = client.get("/rag/stats")
    assert stats.status_code == 200
    assert stats.json()["docs"] == 2

    header_search = client.post("/rag/search", json={"query": "header_unique_signal", "limit": 5})
    page_search = client.post("/rag/search", json={"query": "page_unique_signal", "limit": 5})

    assert any("src/components/index.ts" in str(row) for row in header_search.json())
    assert any("src/pages/index.ts" in str(row) for row in page_search.json())


def test_rag_upload_fallback_db_stays_isolated_per_test(rag_test_env):
    """Primary DB failures should not leak uploads into a shared workspace fallback DB."""
    repo_root = Path(__file__).resolve().parent.parent
    shared_fallback_db = repo_root / ".promptc" / Path(rag_test_env["test_db"]).name
    simple_index.ingest_text(
        "seed.md",
        "shared workspace fallback seed that should stay out of this test",
        db_path=str(shared_fallback_db),
    )

    real_connect = sqlite3.connect
    primary_db = str(Path(rag_test_env["test_db"]))

    def flaky_connect(path, *args, **kwargs):
        resolved = str(Path(path))
        if resolved == primary_db:
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(path, *args, **kwargs)

    with patch("app.rag.simple_index.sqlite3.connect", side_effect=flaky_connect):
        from api.main import app

        with TestClient(app) as client:
            first = client.post(
                "/rag/upload",
                json={
                    "filename": "index.ts",
                    "relative_path": "src/components/index.ts",
                    "content": "export const headerMarker = 'header_unique_signal';",
                },
            )
            second = client.post(
                "/rag/upload",
                json={
                    "filename": "index.ts",
                    "relative_path": "src/pages/index.ts",
                    "content": "export const pageMarker = 'page_unique_signal';",
                },
            )
            stats = client.get("/rag/stats")

    assert first.status_code == 200
    assert second.status_code == 200
    assert stats.status_code == 200
    assert stats.json()["docs"] == 2


def test_rag_upload_with_path_traversal_characters(client):
    """Upload with path traversal characters should sanitize but succeed."""
    response = client.post(
        "/rag/upload",
        json={
            "filename": "../weird/..//a*b?.py",
            "content": "def test_function():\n    return 'This is a test'",
            "force": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ingested_docs"] == 1
    assert data["total_chunks"] >= 1
    assert data["success"] is True
    assert "a*b?.py" in data["message"]


def test_rag_upload_with_unusual_characters(client):
    """Upload with unusual characters should sanitize but succeed."""
    response = client.post(
        "/rag/upload",
        json={
            "filename": "test@file#with$special%chars.py",
            "content": "def special_function():\n    return 42",
            "force": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ingested_docs"] == 1
    assert data["total_chunks"] >= 1
    assert data["success"] is True
    assert "test@file#with$special%chars.py" in data["message"]


def test_rag_upload_fallback_filename(client):
    """Upload with empty or hidden root paths like '.' should fallback to 'upload.txt'."""
    response = client.post(
        "/rag/upload",
        json={
            "filename": ".",
            "content": "test",
            "force": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "upload.txt"
    assert "upload.txt" in data["message"]
