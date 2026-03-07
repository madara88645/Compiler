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


def test_save_exception(tmp_path: Path, monkeypatch) -> None:
    store = ContextPresetStore(path=tmp_path / "presets.json")
    store.upsert("Test", "Data")

    def mock_write_text(*args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    # Should not raise an exception
    store.save()
    store.upsert("Test2", "Data2")
