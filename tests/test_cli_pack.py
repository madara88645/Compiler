from __future__ import annotations

import json

from typer.testing import CliRunner

from cli.main import app as cli_app


runner = CliRunner()


def test_cli_pack_default_md_contains_sections():
    result = runner.invoke(cli_app, ["pack", "hello world"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "# Prompt Pack" in out
    assert "## System Prompt" in out
    assert "## User Prompt" in out
    assert "## Plan" in out
    assert "## Expanded Prompt" in out


def test_cli_pack_json_has_expected_keys():
    result = runner.invoke(cli_app, ["pack", "hello world", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ir_version"] in {"v1", "v2"}
    assert payload["heuristic_version"]
    assert isinstance(payload["system_prompt"], str)
    assert isinstance(payload["user_prompt"], str)
    assert isinstance(payload["plan"], str)
    assert isinstance(payload["expanded_prompt"], str)
