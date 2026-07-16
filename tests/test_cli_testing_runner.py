"""CLI tests for the prompt testing suite runner (`promptc test run`).

Covers: successful suite run, failing assertions, missing suite file,
and malformed YAML.

Fixes #1072.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def _write_suite(tmp_path: Path, prompt_name: str = "prompt.txt") -> Path:
    """Write a minimal valid test suite YAML."""
    suite = {
        "name": "cli-test-suite",
        "prompt_file": prompt_name,
        "defaults": {"name": "User"},
        "test_cases": [
            {
                "id": "tc-pass",
                "input_variables": {"thing": "sandwich"},
                "assertions": [
                    {"type": "not_contains", "value": "FAIL_TOKEN"},
                ],
            }
        ],
    }
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.dump(suite), encoding="utf-8")
    return p


def _write_prompt(tmp_path: Path, name: str = "prompt.txt") -> Path:
    p = tmp_path / name
    p.write_text("Hello {{name}}, please make me a {{thing}}.", encoding="utf-8")
    return p


def test_test_run_passing_suite(tmp_path: Path):
    """A simple suite with a passing assertion should exit 0."""
    _write_prompt(tmp_path)
    suite_path = _write_suite(tmp_path)

    result = runner.invoke(app, ["test", "run", str(suite_path)])

    assert result.exit_code == 0, result.output
    assert "Passed" in result.output or "PASS" in result.output


def test_test_run_failing_assertion(tmp_path: Path):
    """A suite with an assertion that should fail exits non-zero."""
    prompt = _write_prompt(tmp_path)

    suite = {
        "name": "fail-suite",
        "prompt_file": prompt.name,
        "test_cases": [
            {
                "id": "tc-fail",
                "assertions": [
                    # MockExecutor output always contains "MOCKED RESPONSE"
                    # so asserting it must NOT contain that string causes a failure.
                    {"type": "not_contains", "value": "MOCKED RESPONSE"},
                ],
            }
        ],
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.dump(suite), encoding="utf-8")

    result = runner.invoke(app, ["test", "run", str(suite_path)])

    assert result.exit_code != 0


def test_test_run_missing_suite_file(tmp_path: Path):
    """Non-existent suite file path should error out."""
    missing = tmp_path / "missing.yaml"

    result = runner.invoke(app, ["test", "run", str(missing)])

    assert result.exit_code != 0


def test_test_run_malformed_yaml(tmp_path: Path):
    """Invalid YAML in suite file should fail gracefully."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("{{invalid yaml::", encoding="utf-8")

    result = runner.invoke(app, ["test", "run", str(bad)])

    assert result.exit_code != 0


def test_test_run_missing_prompt_file(tmp_path: Path):
    """Suite referencing a non-existent prompt file should report failures."""
    suite = {
        "name": "orphan-suite",
        "prompt_file": "nonexistent_prompt.txt",
        "test_cases": [
            {
                "id": "tc-1",
                "assertions": [{"type": "contains", "value": "anything"}],
            }
        ],
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.dump(suite), encoding="utf-8")

    result = runner.invoke(app, ["test", "run", str(suite_path)])

    # The runner marks all cases as failed when the prompt file is missing
    assert result.exit_code != 0
    assert "FAIL" in result.output or "Failed" in result.output
