"""Test desktop UI settings profiles."""

from __future__ import annotations

import json
import os
import tkinter as tk

import pytest

from ui_desktop import PromptCompilerUI


def _create_root():
    root = tk.Tk()
    try:
        root.withdraw()
    except Exception:
        pass
    return root


def _can_create_tk_window():
    try:
        root = _create_root()
        root.destroy()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true"
    or os.environ.get("PROMPTC_SKIP_GUI_TESTS") == "1"
    or not _can_create_tk_window(),
    reason="Skipping GUI tests in headless environment or when Tkinter is unavailable",
)


@pytest.fixture
def ui_app(tmp_path):
    root = _create_root()
    try:
        app = PromptCompilerUI(root)
        app.config_path = tmp_path / "promptc_ui.json"
        app.settings_profiles = {}
        app.active_settings_profile = None
        app._save_settings()
        yield app
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_save_and_apply_settings_profile_roundtrip(ui_app):
    ui_app.var_diag.set(True)
    ui_app.var_trace.set(False)
    ui_app.var_llm_provider.set("OpenAI")
    ui_app.var_model.set("gpt-4o")

    ui_app._save_settings_profile("Test")

    ui_app.var_diag.set(False)
    ui_app.var_model.set("gpt-4o-mini")

    ui_app._apply_settings_profile("Test")

    assert ui_app.var_diag.get() is True
    assert ui_app.var_model.get() == "gpt-4o"
    assert ui_app.active_settings_profile == "Test"


def test_profiles_persist_to_config_and_reload(tmp_path):
    root1 = _create_root()
    try:
        app1 = PromptCompilerUI(root1)
        app1.config_path = tmp_path / "promptc_ui.json"
        app1.settings_profiles = {}
        app1.active_settings_profile = None
        app1.var_diag.set(True)
        app1._save_settings_profile("Persisted")
        app1._save_settings()

        raw = json.loads(app1.config_path.read_text(encoding="utf-8"))
        assert "settings_profiles" in raw
        assert "Persisted" in raw["settings_profiles"]
        assert raw.get("active_settings_profile") == "Persisted"
    finally:
        try:
            root1.destroy()
        except Exception:
            pass

    root2 = _create_root()
    try:
        app2 = PromptCompilerUI(root2)
        app2.config_path = tmp_path / "promptc_ui.json"
        app2._load_settings()
        assert "Persisted" in app2.settings_profiles
        assert app2.active_settings_profile == "Persisted"
    finally:
        try:
            root2.destroy()
        except Exception:
            pass
