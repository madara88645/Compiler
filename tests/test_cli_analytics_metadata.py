from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import cli.main as cli_main
from cli.main import app as cli_app


runner = CliRunner()


def _capture_analytics(monkeypatch):
    """Capture analytics records without touching the real DB."""
    captured = []

    # Avoid creating ~/.promptc/analytics.db in tests.
    monkeypatch.setattr(cli_main.AnalyticsManager, "__init__", lambda self, db_path=None: None)

    def _record_prompt(self, record):
        captured.append(record)
        return 1

    monkeypatch.setattr(
        cli_main.AnalyticsManager,
        "record_prompt",
        _record_prompt,
    )

    return captured


def test_cli_compile_records_metadata(monkeypatch):
    captured = _capture_analytics(monkeypatch)

    result = runner.invoke(
        cli_app,
        [
            "compile",
            "hello world",
            "--json-only",
            "--record-analytics",
            "--user-level",
            "beginner",
            "--task-type",
            "debugging",
            "--tag",
            "project:x",
            "--tag",
            "foo:bar",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(captured) == 1

    rec = captured[0]
    assert rec.interface_type == "cli"
    assert rec.user_level == "beginner"
    assert rec.task_type == "debugging"
    assert "project:x" in rec.tags
    assert "foo:bar" in rec.tags
    assert rec.iteration_count == 1
    assert rec.time_ms is not None
    assert rec.time_ms >= 0


def test_cli_compile_no_analytics_by_default(monkeypatch):
    captured = _capture_analytics(monkeypatch)

    result = runner.invoke(cli_app, ["compile", "hello world", "--json-only"])

    assert result.exit_code == 0, result.output
    assert captured == []


def test_cli_analytics_record_records_metadata(tmp_path: Path, monkeypatch):
    captured = _capture_analytics(monkeypatch)

    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("teach me recursion", encoding="utf-8")

    result = runner.invoke(
        cli_app,
        [
            "analytics",
            "record",
            str(prompt_file),
            "--no-validate",
            "--user-level",
            "advanced",
            "--task-type",
            "teaching",
            "--tag",
            "source:test",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(captured) == 1

    rec = captured[0]
    assert rec.interface_type == "cli"
    assert rec.user_level == "advanced"
    assert rec.task_type == "teaching"
    assert "source:test" in rec.tags
    assert rec.iteration_count == 1
    assert rec.time_ms is not None
    assert rec.time_ms >= 0
