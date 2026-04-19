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
