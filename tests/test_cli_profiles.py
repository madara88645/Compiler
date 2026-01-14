from __future__ import annotations

import json

from typer.testing import CliRunner

from cli.main import app as cli_app


runner = CliRunner()


def test_cli_profile_save_list_show_activate_delete(tmp_path, monkeypatch):
    cfg = tmp_path / "ui_config.json"
    monkeypatch.setenv("PROMPTC_UI_CONFIG", str(cfg))

    # Seed a config that `profile save` can snapshot.
    cfg.write_text(
        json.dumps(
            {
                "diagnostics": True,
                "trace": False,
                "model": "gpt-4o-mini",
                "llm_provider": "OpenAI",
                "rag_method": "fts",
                "optimize_max_chars": "123",
                "optimize_max_tokens": "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(cli_app, ["profile", "save", "Work"])
    assert result.exit_code == 0, result.output

    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert payload.get("active_settings_profile") == "Work"
    assert "settings_profiles" in payload
    assert "Work" in payload["settings_profiles"]
    assert payload["settings_profiles"]["Work"]["diagnostics"] is True
    assert payload["settings_profiles"]["Work"]["rag_method"] == "fts"
    assert payload["settings_profiles"]["Work"]["optimize_max_chars"] == "123"

    result = runner.invoke(cli_app, ["profile", "list", "--json"])
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["active"] == "Work"
    assert "Work" in out["profiles"]

    result = runner.invoke(cli_app, ["profile", "show", "Work"])
    assert result.exit_code == 0, result.output
    shown = json.loads(result.output)
    assert shown["model"] == "gpt-4o-mini"

    # Activate (idempotent)
    result = runner.invoke(cli_app, ["profile", "activate", "Work"])
    assert result.exit_code == 0, result.output

    # Rename
    result = runner.invoke(cli_app, ["profile", "rename", "Work", "Work2"])
    assert result.exit_code == 0, result.output
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert payload.get("active_settings_profile") == "Work2"
    assert "Work2" in payload.get("settings_profiles", {})

    # Delete
    result = runner.invoke(cli_app, ["profile", "delete", "Work2"])
    assert result.exit_code == 0, result.output
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert "Work2" not in payload.get("settings_profiles", {})


def test_cli_profile_export_import_roundtrip(tmp_path, monkeypatch):
    cfg = tmp_path / "ui_config.json"
    monkeypatch.setenv("PROMPTC_UI_CONFIG", str(cfg))

    cfg.write_text(
        json.dumps(
            {
                "diagnostics": True,
                "trace": False,
                "model": "gpt-4o-mini",
                "llm_provider": "OpenAI",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(cli_app, ["profile", "save", "Work"])
    assert result.exit_code == 0, result.output

    export_path = tmp_path / "work.json"
    result = runner.invoke(cli_app, ["profile", "export", "Work", "-o", str(export_path)])
    assert result.exit_code == 0, result.output
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["schema"] == "promptc.settings_profile"
    assert exported["name"] == "Work"
    assert exported["profile"]["model"] == "gpt-4o-mini"

    # Delete then import
    result = runner.invoke(cli_app, ["profile", "delete", "Work"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli_app, ["profile", "import", str(export_path)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "Work"

    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert "Work" in payload.get("settings_profiles", {})


def test_cli_profile_clear_active(tmp_path, monkeypatch):
    cfg = tmp_path / "ui_config.json"
    monkeypatch.setenv("PROMPTC_UI_CONFIG", str(cfg))

    cfg.write_text(
        json.dumps(
            {
                "settings_profiles": {"A": {"diagnostics": False}},
                "active_settings_profile": "A",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(cli_app, ["profile", "clear"])
    assert result.exit_code == 0, result.output

    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert payload.get("active_settings_profile") in (None, "")
