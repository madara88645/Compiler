from pathlib import Path

from app.rag.history_store import RAGHistoryStore


def test_add_and_limit_queries(tmp_path: Path) -> None:
    store = RAGHistoryStore(path=tmp_path / "hist.json", max_queries=3)
    for i in range(5):
        store.add_query(f"query {i}", "fts", i + 1)
    assert len(store.queries) == 3
    assert store.queries[0].query == "query 2"
    store.delete_query(1)
    assert len(store.queries) == 2
    store.clear_queries()
    assert store.queries == []


def test_add_pins_and_persist(tmp_path: Path) -> None:
    path = tmp_path / "hist.json"
    store = RAGHistoryStore(path=path, max_pins=2)
    store.add_pin("first", "snippet one", "doc1")
    store.add_pin("second", "snippet two", "doc2")
    store.add_pin("third", "snippet three", "doc3")
    assert len(store.pins) == 2
    assert store.pins[0].label == "second"
    store.delete_pin(0)
    assert len(store.pins) == 1
    store.clear_pins()
    assert store.pins == []

    # reload from disk ensures no crash
    store.save()
    reloaded = RAGHistoryStore(path=path)
    assert reloaded.queries == []
    assert reloaded.pins == []
