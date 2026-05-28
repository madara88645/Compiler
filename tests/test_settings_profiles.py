"""Tests for UI settings profile persistence (app.settings_profiles)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.settings_profiles import (
    ACTIVE_SETTINGS_PROFILE_KEY,
    SETTINGS_PROFILES_KEY,
    ProfilesSnapshot,
    delete_profile,
    duplicate_active_profile,
    export_profile_to_path,
    get_profile,
    import_profile_from_path,
    load_profiles_snapshot,
    load_ui_config,
    rename_profile,
    save_profiles_snapshot,
    set_active_profile,
    upsert_profile,
)


@pytest.fixture
def ui_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "promptc_ui.json"
    monkeypatch.setenv("PROMPTC_UI_CONFIG", str(path))
    return path


def test_load_ui_config_missing_file_returns_empty(ui_config_path: Path) -> None:
    assert not ui_config_path.exists()
    assert load_ui_config() == {}


def test_load_ui_config_corrupt_json_returns_empty(ui_config_path: Path) -> None:
    ui_config_path.write_text("{not valid json", encoding="utf-8")
    assert load_ui_config() == {}


def test_save_profiles_snapshot_preserves_unrelated_config_keys(ui_config_path: Path) -> None:
    ui_config_path.write_text(
        json.dumps({"theme": "dark", "sidebar": True}),
        encoding="utf-8",
    )
    save_profiles_snapshot(
        ProfilesSnapshot(
            profiles={"work": {"model": "gpt-4"}},
            active="work",
        )
    )
    config = json.loads(ui_config_path.read_text(encoding="utf-8"))
    assert config["theme"] == "dark"
    assert config["sidebar"] is True
    assert config[SETTINGS_PROFILES_KEY] == {"work": {"model": "gpt-4"}}
    assert config[ACTIVE_SETTINGS_PROFILE_KEY] == "work"


def test_upsert_get_and_list_roundtrip(ui_config_path: Path) -> None:
    upsert_profile("  Alpha  ", {"temperature": 0.2}, set_active=True)
    assert get_profile("Alpha") == {"temperature": 0.2}
    snap = load_profiles_snapshot()
    assert snap.active == "Alpha"
    assert "Alpha" in snap.profiles


def test_load_profiles_snapshot_skips_non_dict_entries(ui_config_path: Path) -> None:
    ui_config_path.write_text(
        json.dumps(
            {
                SETTINGS_PROFILES_KEY: {
                    "valid": {"k": 1},
                    "bad": "not-a-dict",
                    "": {"ignored": True},
                    "  spaced  ": {"k": 2},
                }
            }
        ),
        encoding="utf-8",
    )
    snap = load_profiles_snapshot()
    assert snap.profiles == {"valid": {"k": 1}, "spaced": {"k": 2}}


def test_delete_active_profile_clears_active_pointer(ui_config_path: Path) -> None:
    upsert_profile("temp", {"x": 1}, set_active=True)
    assert delete_profile("temp") is True
    snap = load_profiles_snapshot()
    assert "temp" not in snap.profiles
    assert snap.active is None


def test_rename_profile_moves_active_pointer(ui_config_path: Path) -> None:
    upsert_profile("old", {"flag": True}, set_active=True)
    assert rename_profile("old", "new") is True
    snap = load_profiles_snapshot()
    assert snap.active == "new"
    assert get_profile("new") == {"flag": True}
    assert get_profile("old") is None


def test_rename_profile_fails_when_target_exists(ui_config_path: Path) -> None:
    upsert_profile("a", {"v": 1}, set_active=False)
    upsert_profile("b", {"v": 2}, set_active=False)
    assert rename_profile("a", "b") is False
    assert get_profile("a") == {"v": 1}
    assert get_profile("b") == {"v": 2}


def test_set_active_profile_unknown_raises_key_error(ui_config_path: Path) -> None:
    with pytest.raises(KeyError, match="Profile not found"):
        set_active_profile("missing")


def test_duplicate_active_profile_without_active_raises(ui_config_path: Path) -> None:
    upsert_profile("solo", {"k": 1}, set_active=False)
    set_active_profile(None)
    with pytest.raises(ValueError, match="No active profile"):
        duplicate_active_profile("copy")


def test_export_and_import_profile_roundtrip(ui_config_path: Path, tmp_path: Path) -> None:
    upsert_profile("portable", {"mode": "conservative"}, set_active=True)
    export_path = tmp_path / "profile.json"
    payload = export_profile_to_path("portable", export_path)
    assert payload["schema"] == "promptc.settings_profile"
    assert export_path.exists()

    upsert_profile("portable", {"mode": "default"}, set_active=True)
    imported = import_profile_from_path(export_path)
    assert imported == "portable"
    assert get_profile("portable") == {"mode": "conservative"}
    assert load_profiles_snapshot().active == "portable"


def test_import_profile_rejects_unsupported_schema(ui_config_path: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"schema": "other", "name": "x", "profile": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsupported profile schema"):
        import_profile_from_path(bad)


def test_upsert_profile_empty_name_raises(ui_config_path: Path) -> None:
    with pytest.raises(ValueError, match="Profile name is required"):
        upsert_profile("   ", {"k": 1})
