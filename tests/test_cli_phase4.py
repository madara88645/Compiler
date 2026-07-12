"""Phase 4 (CLI PR Safety) tests.

Cover the ``pr-safety`` command: manual mode across all three output formats,
verdict-driving inputs (split / rebase / merge), ``--exit-code`` behavior,
error paths, and ``--from-git`` mode via monkeypatched git helpers. Fully
offline and deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import cli.commands.pr_safety as pr_safety_mod
from app.pr_safety.models import PrSafetyReport, RepoSignalsSection
from cli.main import app as main_app

_runner = CliRunner()


def _invoke(args, **kwargs):
    return _runner.invoke(main_app, args, **kwargs)


def test_human_format_shows_verdict():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "app/foo.py",
            "tests/test_foo.py",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "MERGE" in result.output
    assert "PR Safety" in result.output
    assert "Recommendations" in result.output


def test_json_format_round_trips_to_report():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "app/foo.py",
            "tests/test_foo.py",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    report = PrSafetyReport(**data)
    assert report.verdict == "merge"
    assert report.changed_files.total == 2


def test_md_format_starts_with_header_and_sections():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "app/foo.py",
            "--format",
            "md",
        ]
    )
    assert result.exit_code == 0, result.output
    out = result.output
    assert out.lstrip().startswith("# PR Safety Report")
    assert "## Changed files" in out
    assert "## Risky areas" in out
    assert "## Branch freshness" in out
    assert "## Test coverage" in out
    assert "## Scope match" in out
    assert "## Recommendations" in out
    assert "offline heuristic advisory" in out


def test_verdict_split_on_large_changeset():
    files = [f"pkg/mod_{i}.py" for i in range(20)]
    result = _invoke(
        ["pr-safety", "-t", "change stuff", "--description", "do things", "--format", "json"]
        + files
    )
    assert result.exit_code == 0, result.output
    report = PrSafetyReport(**json.loads(result.output))
    assert report.verdict == "split"


def test_verdict_rebase_on_stale_branch():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc",
            "app/foo.py",
            "tests/test_foo.py",
            "--commits-behind",
            "12",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.output
    report = PrSafetyReport(**json.loads(result.output))
    assert report.verdict == "rebase"


def test_verdict_merge_on_clean_small_change():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "app/foo.py",
            "tests/test_foo.py",
            "--commits-behind",
            "0",
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.output
    report = PrSafetyReport(**json.loads(result.output))
    assert report.verdict == "merge"


def test_exit_code_flag_returns_one_on_non_merge():
    files = [f"pkg/mod_{i}.py" for i in range(20)]
    result = _invoke(["pr-safety", "-t", "x", "--description", "y", "--exit-code"] + files)
    assert result.exit_code == 1, result.output


def test_exit_code_flag_returns_zero_on_merge():
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "app/foo.py",
            "tests/test_foo.py",
            "--commits-behind",
            "0",
            "--exit-code",
        ]
    )
    assert result.exit_code == 0, result.output


def test_missing_title_errors_without_from_git():
    result = _invoke(["pr-safety", "--description", "y", "app/foo.py"])
    assert result.exit_code != 0
    assert "title" in result.output.lower()


def test_missing_description_errors_without_from_git():
    result = _invoke(["pr-safety", "-t", "x", "app/foo.py"])
    assert result.exit_code != 0
    assert "description" in result.output.lower()


def test_files_from_reads_newline_delimited(tmp_path):
    listing = tmp_path / "files.txt"
    listing.write_text("app/foo.py\ntests/test_foo.py\n", encoding="utf-8")
    result = _invoke(
        [
            "pr-safety",
            "-t",
            "Add foo",
            "--description",
            "desc body",
            "--files-from",
            str(listing),
            "--format",
            "json",
        ]
    )
    assert result.exit_code == 0, result.output
    report = PrSafetyReport(**json.loads(result.output))
    assert report.changed_files.total == 2


def test_from_git_mode_uses_monkeypatched_helpers(monkeypatch):
    monkeypatch.setattr(pr_safety_mod, "resolve_base_ref", lambda base: "origin/main")
    monkeypatch.setattr(
        pr_safety_mod,
        "git_changed_files",
        lambda base: ["app/foo.py", "tests/test_foo.py"],
    )
    monkeypatch.setattr(pr_safety_mod, "git_commits_behind", lambda base: 0)
    monkeypatch.setattr(pr_safety_mod, "head_commit_message", lambda: ("Add foo", "body text"))
    monkeypatch.setattr(pr_safety_mod, "repository_root", lambda: Path("/repo"))
    monkeypatch.setattr(
        pr_safety_mod,
        "collect_repo_signals",
        lambda root, files: RepoSignalsSection(source="local_checkout"),
    )

    result = _invoke(["pr-safety", "--from-git", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    report = PrSafetyReport(**payload)
    assert report.title == "Add foo"
    assert report.verdict == "merge"
    assert payload["repo_signals"]["source"] == "local_checkout"


def test_from_git_mode_stale_branch_yields_rebase(monkeypatch):
    monkeypatch.setattr(pr_safety_mod, "resolve_base_ref", lambda base: "main")
    monkeypatch.setattr(pr_safety_mod, "git_changed_files", lambda base: ["app/foo.py"])
    monkeypatch.setattr(pr_safety_mod, "git_commits_behind", lambda base: 15)
    monkeypatch.setattr(pr_safety_mod, "head_commit_message", lambda: ("Add foo", "body"))

    result = _invoke(["pr-safety", "--from-git", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = PrSafetyReport(**json.loads(result.output))
    assert report.verdict == "rebase"


def test_from_git_error_exits_nonzero(monkeypatch):
    from app.pr_safety.git_context import GitContextError

    def _boom(base):
        raise GitContextError("not a git repository")

    monkeypatch.setattr(pr_safety_mod, "resolve_base_ref", _boom)
    result = _invoke(["pr-safety", "--from-git"])
    assert result.exit_code == 1
    assert "git error" in result.output.lower()
