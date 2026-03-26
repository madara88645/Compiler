import os
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


def test_pack_respects_max_tokens_api():
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "idx.db")
        p = os.path.join(td, "a.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(("token " * 800).strip())
        with (
            patch("app.rag.simple_index.DEFAULT_DB_PATH", db_path),
            patch.dict(os.environ, {"PROMPTC_RAG_ALLOWED_ROOTS": td}, clear=False),
        ):
            r = client.post("/rag/ingest", json={"paths": [p]})
            assert r.status_code == 200

            pack = client.post(
                "/rag/pack",
                json={
                    "query": "token",
                    "k": 5,
                    "method": "fts",
                    "max_tokens": 100,
                    "token_ratio": 4.0,
                },
            )
            assert pack.status_code == 200, pack.text
            data = pack.json()
            assert data.get("tokens") is not None
            assert data["tokens"] <= 100
            assert data["chars"] >= data["tokens"]


def test_pack_respects_max_tokens_cli_snapshot():
    # Directly exercise pack function via API is enough; CLI path is thin wrapper.
    # This test ensures ingest with embeddings doesn't break token packing.
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "idx.db")
        p = os.path.join(td, "b.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(("lorem ipsum " * 600).strip())
        with (
            patch("app.rag.simple_index.DEFAULT_DB_PATH", db_path),
            patch.dict(os.environ, {"PROMPTC_RAG_ALLOWED_ROOTS": td}, clear=False),
        ):
            r = client.post(
                "/rag/ingest",
                json={"paths": [p], "embed": True, "embed_dim": 32},
            )
            assert r.status_code == 200
            pack = client.post(
                "/rag/pack",
                json={
                    "query": "ipsum",
                    "k": 5,
                    "method": "hybrid",
                    "embed_dim": 32,
                    "alpha": 0.5,
                    "max_tokens": 120,
                    "token_ratio": 4.0,
                },
            )
            assert pack.status_code == 200
            data = pack.json()
            assert data["tokens"] <= 120
