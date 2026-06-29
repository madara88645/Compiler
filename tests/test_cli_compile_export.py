"""Threshold tests for the CLI `compile-export` command (Codex task).

Definition of done: add a `compile-export` CLI command that produces the same
executable .md / .json bundle as the POST /compile/export endpoint (#887), but
written to disk (or stdout) from the command line. The command must run fully
offline/deterministically (no LLM/network), like the existing CLI compile path.

Do NOT modify, weaken, or delete any assertion in this file. The full existing
suite must also stay green.

Contract being locked in:
  * `compile-export TEXT`                  -> prints the export markdown to stdout.
  * `compile-export TEXT --out-dir DIR`    -> writes DIR/compile-export.md and
                                              DIR/compile-export.json.
  * The markdown has the same sections as /compile/export:
    `## System Prompt`, `## User Prompt`, `## Plan`, `## Readiness:`.
  * The JSON carries at least `readiness` (with `verdict`), `system_prompt`,
    `user_prompt`, `plan`.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli.commands._base import app

runner = CliRunner()

# A prompt with a non-trivial readiness verdict ("clarify"), so sections are never empty.
EXPORT_TEXT = "use the AcmeCloud SDK to deploy my model"
VALID_VERDICTS = {"ready", "clarify", "risky", "noise"}


def test_compile_export_to_stdout_has_all_sections():
    result = runner.invoke(app, ["compile-export", EXPORT_TEXT])
    assert result.exit_code == 0, result.output
    out = result.stdout
    assert "## System Prompt" in out
    assert "## User Prompt" in out
    assert "## Plan" in out
    assert "## Readiness:" in out


def test_compile_export_writes_md_and_json(tmp_path: Path):
    result = runner.invoke(app, ["compile-export", EXPORT_TEXT, "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    md = tmp_path / "compile-export.md"
    js = tmp_path / "compile-export.json"
    assert md.exists(), "expected compile-export.md to be written"
    assert js.exists(), "expected compile-export.json to be written"

    md_text = md.read_text(encoding="utf-8")
    assert "## System Prompt" in md_text
    assert "## User Prompt" in md_text
    assert "## Plan" in md_text
    assert "## Readiness:" in md_text


def test_compile_export_json_is_valid_and_structured(tmp_path: Path):
    result = runner.invoke(app, ["compile-export", EXPORT_TEXT, "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "compile-export.json").read_text(encoding="utf-8"))
    assert isinstance(data.get("readiness"), dict)
    assert data["readiness"].get("verdict") in VALID_VERDICTS
    for key in ("system_prompt", "user_prompt", "plan"):
        assert key in data, f"export json missing '{key}'"


def test_compile_export_markdown_embeds_real_prompt(tmp_path: Path):
    result = runner.invoke(app, ["compile-export", EXPORT_TEXT, "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "compile-export.json").read_text(encoding="utf-8"))
    md_text = (tmp_path / "compile-export.md").read_text(encoding="utf-8")
    # Anti-gaming: the export must embed the real compiled system prompt, not a placeholder.
    assert data["system_prompt"][:30] in md_text
