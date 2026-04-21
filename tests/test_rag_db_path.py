import sqlite3
from pathlib import Path

from app.rag import simple_index


def test_default_rag_db_path_honors_env_override(tmp_path, monkeypatch):
    fallback_db = tmp_path / "fallback.db"
    env_db = tmp_path / "isolated" / "rag.db"
    unique_term = "env_db_path_unique_signal"

    monkeypatch.setattr(simple_index, "DEFAULT_DB_PATH", str(fallback_db))
    monkeypatch.setenv("PROMPTC_RAG_DB_PATH", str(env_db))

    simple_index.ingest_text("notes.md", f"Project notes mention {unique_term}.")

    assert env_db.exists()
    assert not fallback_db.exists()
    assert any(unique_term in item["snippet"] for item in simple_index.search(unique_term, k=3))
    assert simple_index.stats()["docs"] == 1


def test_default_rag_db_path_falls_back_to_workspace_when_primary_is_unwritable(
    tmp_path, monkeypatch
):
    primary_db = tmp_path / "blocked" / "rag.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    unique_term = "workspace_fallback_signal"

    monkeypatch.delenv("PROMPTC_RAG_DB_PATH", raising=False)
    monkeypatch.setattr(simple_index, "DEFAULT_DB_PATH", str(primary_db))
    monkeypatch.chdir(workspace)

    real_connect = sqlite3.connect
    attempted_paths: list[str] = []

    def flaky_connect(path, *args, **kwargs):
        resolved = str(Path(path))
        attempted_paths.append(resolved)
        if resolved == str(primary_db):
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(simple_index.sqlite3, "connect", flaky_connect)

    simple_index.ingest_text("notes.md", f"Project notes mention {unique_term}.")

    fallback_db = workspace / ".promptc" / primary_db.name
    assert fallback_db.exists()
    assert attempted_paths[0] == str(primary_db)
    assert str(fallback_db) in attempted_paths
    assert any(unique_term in item["snippet"] for item in simple_index.search(unique_term, k=3))
