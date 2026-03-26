"""Test the stabilized /rag upload/search endpoints."""

import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client, patching startup to skip HybridCompiler."""
    with tempfile.TemporaryDirectory() as td:
        test_db = os.path.join(td, "test_upload.db")
        upload_dir = os.path.join(td, "uploads")

        with (
            patch("app.rag.simple_index.DEFAULT_DB_PATH", test_db),
            patch.dict(
                os.environ,
                {
                    "PROMPTC_UPLOAD_DIR": upload_dir,
                    "PROMPTC_RAG_ALLOWED_ROOTS": td,
                },
                clear=False,
            ),
        ):
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
