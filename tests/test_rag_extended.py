from __future__ import annotations
import json
from pathlib import Path
from typer.testing import CliRunner
from fastapi.testclient import TestClient
from cli.main import app as cli_app
from api.main import app as api_app

runner = CliRunner()
client = TestClient(api_app)


def prepare_source(tmp_path: Path) -> Path:
    src = tmp_path / "rag_src"
    src.mkdir()
    (src / "keep.txt").write_text("machine learning optimizers like adam and sgd", encoding="utf-8")
    (src / "drop.txt").write_text("temporary file to be removed", encoding="utf-8")
    return src


def test_cli_stats_and_prune(tmp_path: Path):
    src = prepare_source(tmp_path)
    db = tmp_path / "idx.db"
    # initial ingest
    r = runner.invoke(cli_app, ["rag", "index", str(src), "--db-path", str(db)])
    assert r.exit_code == 0, r.output
    # stats json
    s = runner.invoke(cli_app, ["rag", "stats", "--db-path", str(db), "--json"])
    assert s.exit_code == 0
    stats_payload = json.loads(s.output)
    assert stats_payload["docs"] >= 2
    # remove one file then prune
    (src / "drop.txt").unlink()
    p = runner.invoke(cli_app, ["rag", "prune", "--db-path", str(db), "--json"])
    assert p.exit_code == 0
    pr = json.loads(p.output)
    assert pr["removed_docs"] >= 1


def test_api_rag_cycle(tmp_path: Path):
    src = prepare_source(tmp_path)
    db = str(tmp_path / "api_idx.db")
    # ingest
    resp = client.post("/rag/ingest", json={"paths": [str(src)], "db_path": db})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ingested_docs"] >= 2
    # query
    q = client.post("/rag/query", json={"query": "optimizers", "k": 3, "db_path": db})
    assert q.status_code == 200
    qd = q.json()
    assert qd["count"] >= 1
    # stats
    st = client.post("/rag/stats", json={"db_path": db})
    assert st.status_code == 200
    stj = st.json()
    assert stj["docs"] >= 2
    # prune (delete a file then prune)
    Path(src / "drop.txt").unlink()
    pr = client.post("/rag/prune", json={"db_path": db})
    assert pr.status_code == 200
    prd = pr.json()
    assert prd["removed_docs"] >= 1
