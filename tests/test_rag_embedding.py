import json
from pathlib import Path
from typer.testing import CliRunner
from cli.main import app as cli_app
from fastapi.testclient import TestClient
from api.main import app as api_app

runner = CliRunner()


def test_cli_embedding_roundtrip(tmp_path: Path):
    # create sample docs with overlapping vocabulary
    (tmp_path / "doc1.txt").write_text("alpha beta gamma delta epsilon", encoding="utf-8")
    (tmp_path / "doc2.txt").write_text("alpha beta zeta eta theta", encoding="utf-8")
    db_path = tmp_path / "rag.db"
    # ingest with embeddings
    r = runner.invoke(
        cli_app, ["rag", "index", str(tmp_path), "--db-path", str(db_path), "--embed"]
    )
    assert r.exit_code == 0, r.output
    # embedding query
    qr = runner.invoke(
        cli_app,
        ["rag", "query", "alpha beta", "--db-path", str(db_path), "--method", "embed", "--json"],
    )
    assert qr.exit_code == 0, qr.output
    data = json.loads(qr.output)
    assert isinstance(data, list)
    assert data, "Expected results"
    # similarity field present
    assert "similarity" in data[0]
    # lexical query still works
    lr = runner.invoke(
        cli_app,
        ["rag", "query", "alpha beta", "--db-path", str(db_path), "--method", "fts", "--json"],
    )
    assert lr.exit_code == 0, lr.output
    ldata = json.loads(lr.output)
    assert isinstance(ldata, list)


def test_api_embedding(tmp_path: Path):
    d1 = tmp_path / "a.txt"
    d2 = tmp_path / "b.txt"
    d1.write_text("red green blue yellow", encoding="utf-8")
    d2.write_text("red green cyan magenta", encoding="utf-8")
    db_path = str(tmp_path / "api.db")
    client = TestClient(api_app)
    # ingest with embeddings
    res = client.post(
        "/rag/ingest", json={"paths": [str(tmp_path)], "db_path": db_path, "embed": True}
    )
    assert res.status_code == 200, res.text
    j = res.json()
    assert j["ingested_docs"] >= 2
    # embed query
    q = client.post(
        "/rag/query", json={"query": "red green", "db_path": db_path, "method": "embed"}
    )
    assert q.status_code == 200, q.text
    qj = q.json()
    assert qj["count"] > 0
    assert "similarity" in qj["results"][0]
    # fts fallback
    q2 = client.post("/rag/query", json={"query": "red green", "db_path": db_path, "method": "fts"})
    assert q2.status_code == 200
    q2j = q2.json()
    assert q2j["count"] > 0
