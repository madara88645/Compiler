"""Test the /rag/upload SaaS endpoint using FastAPI TestClient."""

import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client, patching startup to skip HybridCompiler."""
    # Use a temp DB so we don't conflict with any locked production DB
    test_db = os.path.join(os.path.dirname(__file__), "_test_upload.db")

    # Patch the default DB path so we don't touch the real one
    with patch("app.rag.simple_index.DEFAULT_DB_PATH", test_db):
        from api.main import app

        with TestClient(app) as c:
            yield c

    # Cleanup
    for f in [test_db, test_db + "-journal", test_db + "-wal", test_db + "-shm"]:
        if os.path.exists(f):
            os.unlink(f)


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
    assert data["success"] is True
    assert data["num_chunks"] >= 1
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
    response = client.post(
        "/rag/search", json={"query": "multiply", "limit": 3, "method": "keyword"}
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    # At least one result should mention multiply
    found = any("multiply" in str(r) for r in results)
    assert found, f"Expected 'multiply' in results: {results}"
