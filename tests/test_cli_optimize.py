"""Unit tests for CLI evolutionary prompt optimization commands.

Covers: optimize run (with --dry-run), optimize history list, optimize history show.
All tests use the mock provider or mocked engines — no real LLM calls.

Fixes #1038.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def _write_prompt_file(tmp_path: Path, content: str = "Summarize a document") -> Path:
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return p


def _write_suite_file(tmp_path: Path, prompt_file: str = "prompt.txt") -> Path:
    suite_data = {
        "name": "test-suite",
        "prompt_file": prompt_file,
        "test_cases": [
            {
                "id": "tc-1",
                "description": "Basic summary check",
                "input_variables": {"doc": "A short document"},
                "assertions": [
                    {"type": "contains", "value": "summary"},
                ],
            }
        ],
    }
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.dump(suite_data), encoding="utf-8")
    return p


def test_optimize_run_dry_run(tmp_path: Path):
    """--dry-run should estimate cost and exit without running the engine."""
    prompt = _write_prompt_file(tmp_path)
    suite = _write_suite_file(tmp_path, prompt_file=str(prompt))

    result = runner.invoke(
        app,
        [
            "optimize",
            "run",
            str(prompt),
            str(suite),
            "--dry-run",
            "--provider",
            "mock",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Estimated Cost" in result.output or "Dry Run Estimate" in result.output


def test_optimize_run_missing_prompt_file(tmp_path: Path):
    """Should fail gracefully when prompt file does not exist."""
    suite = _write_suite_file(tmp_path)
    missing = tmp_path / "nonexistent.txt"

    result = runner.invoke(
        app,
        ["optimize", "run", str(missing), str(suite), "--provider", "mock"],
    )

    assert result.exit_code != 0


def test_optimize_run_missing_suite_file(tmp_path: Path):
    """Should fail gracefully when suite file does not exist."""
    prompt = _write_prompt_file(tmp_path)
    missing = tmp_path / "nonexistent.yaml"

    result = runner.invoke(
        app,
        ["optimize", "run", str(prompt), str(missing), "--provider", "mock"],
    )

    assert result.exit_code != 0


def test_optimize_history_list_empty(tmp_path: Path):
    """history list should print an empty-state message when no history exists."""
    with patch("app.optimizer.history.HistoryManager") as MockHM:
        mock_manager = MagicMock()
        mock_manager.list_runs.return_value = []
        MockHM.return_value = mock_manager

        result = runner.invoke(app, ["optimize", "history", "list"])

    assert result.exit_code == 0
    assert "no history" in result.output.lower() or "History" in result.output


def test_optimize_history_list_with_runs(tmp_path: Path):
    """history list should display runs in a table."""
    with patch("app.optimizer.history.HistoryManager") as MockHM:
        mock_manager = MagicMock()
        mock_manager.list_runs.return_value = [
            {
                "id": "abc12345-6789-0000-0000-000000000000",
                "date": "2026-07-10",
                "best_score": 0.85,
                "model": "mock",
                "generations": 3,
            }
        ]
        MockHM.return_value = mock_manager

        result = runner.invoke(app, ["optimize", "history", "list"])

    assert result.exit_code == 0
    assert "abc12345" in result.output
    assert "0.85" in result.output


def test_optimize_history_show_not_found():
    """history show should fail when the run ID does not exist."""
    with patch("app.optimizer.history.HistoryManager") as MockHM:
        mock_manager = MagicMock()
        mock_manager.load_run.return_value = None
        mock_manager.list_runs.return_value = []
        MockHM.return_value = mock_manager

        result = runner.invoke(app, ["optimize", "history", "show", "nonexistent"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()
