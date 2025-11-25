from pathlib import Path

from app.context_presets import ContextPresetStore


def test_upsert_and_persist(tmp_path: Path) -> None:
    store = ContextPresetStore(path=tmp_path / "presets.json")
    store.upsert("Default", "Hello")
    store.upsert("Default", "Updated")
    store.upsert("Notes", "Other text")
    assert store.get("Default").content == "Updated"
    assert set(store.list_names()) == {"Default", "Notes"}

    store2 = ContextPresetStore(path=tmp_path / "presets.json")
    assert store2.get("Default").content == "Updated"


def test_delete_and_rename(tmp_path: Path) -> None:
    store = ContextPresetStore(path=tmp_path / "presets.json")
    store.upsert("Alpha", "A")
    store.upsert("Beta", "B")
    assert store.rename("Alpha", "Gamma") is True
    assert store.get("Gamma").content == "A"
    assert store.delete("Beta") is True
    assert store.get("Beta") is None
    assert store.delete("Missing") is False
