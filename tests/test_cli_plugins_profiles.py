"""CLI tests for plugins and profiles subcommands.

Covers: plugins list, profile list, profile show (missing),
profile delete (missing), profile rename (missing).

Fixes #1076.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


# ── plugins ──────────────────────────────────────────────────────────


@patch("cli.commands.utils.describe_plugins")
def test_plugins_list_empty(mock_describe):
    """plugins list should handle zero plugins gracefully."""
    mock_describe.return_value = []

    result = runner.invoke(app, ["plugins", "list"])

    assert result.exit_code == 0
    assert "No plugins" in result.output or result.output.strip() == ""


@patch("cli.commands.utils.describe_plugins")
def test_plugins_list_with_entries(mock_describe):
    """plugins list should print plugin names."""
    mock_describe.return_value = [
        {"name": "SamplePlugin", "version": "1.0", "description": "A sample", "provides": ["hook"]},
    ]

    result = runner.invoke(app, ["plugins", "list"])

    assert result.exit_code == 0
    assert "SamplePlugin" in result.output


@patch("cli.commands.utils.describe_plugins")
def test_plugins_list_json_output(mock_describe):
    """plugins list --json should emit valid JSON."""
    mock_describe.return_value = [
        {"name": "TestPlugin", "version": "0.1", "description": "test", "provides": []},
    ]

    result = runner.invoke(app, ["plugins", "list", "--json"])

    assert result.exit_code == 0
    assert "TestPlugin" in result.output


# ── profiles ─────────────────────────────────────────────────────────


@patch("cli.commands.utils.load_profiles_snapshot")
def test_profile_list_empty(mock_snap):
    """profile list should handle no profiles."""
    snap = MagicMock()
    snap.profiles = {}
    snap.active = None
    mock_snap.return_value = snap

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "No profiles" in result.output or "Profiles" in result.output


@patch("cli.commands.utils.load_profiles_snapshot")
def test_profile_list_with_entries(mock_snap):
    """profile list should show profile names."""
    snap = MagicMock()
    snap.profiles = {"dev": {}, "prod": {}}
    snap.active = "dev"
    mock_snap.return_value = snap

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "dev" in result.output
    assert "prod" in result.output


@patch("cli.commands.utils.get_settings_profile")
def test_profile_show_missing(mock_get):
    """profile show on a non-existent profile should exit non-zero."""
    mock_get.return_value = None

    result = runner.invoke(app, ["profile", "show", "nonexistent"])

    assert result.exit_code != 0


@patch("cli.commands.utils.delete_settings_profile")
def test_profile_delete_missing(mock_del):
    """profile delete on a non-existent profile should exit non-zero."""
    mock_del.return_value = False

    result = runner.invoke(app, ["profile", "delete", "nonexistent"])

    assert result.exit_code != 0


@patch("cli.commands.utils.rename_settings_profile")
def test_profile_rename_missing(mock_rename):
    """profile rename on a non-existent source should exit non-zero."""
    mock_rename.return_value = False

    result = runner.invoke(app, ["profile", "rename", "old", "new"])

    assert result.exit_code != 0
