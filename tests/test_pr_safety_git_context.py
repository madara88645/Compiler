"""Direct unit tests for PR Safety git inspection helpers.

These tests avoid real git state and instead verify the command shapes,
parsing, and error handling that ``pr-safety --from-git`` depends on.
"""

from __future__ import annotations

import subprocess

import pytest

from app.pr_safety.git_context import (
    GitContextError,
    _run_git,
    changed_files,
    commits_behind,
    head_commit_message,
    resolve_base_ref,
)


def _completed(args: list[str], *, stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def test_resolve_base_ref_prefers_first_available_candidate(monkeypatch):
    seen: list[str] = []

    def fake_ref_exists(ref: str) -> bool:
        seen.append(ref)
        return ref == "main"

    monkeypatch.setattr("app.pr_safety.git_context._ref_exists", fake_ref_exists)

    assert resolve_base_ref(None) == "main"
    assert seen == ["origin/main", "origin/master", "main"]


def test_resolve_base_ref_rejects_unknown_explicit_base(monkeypatch):
    monkeypatch.setattr("app.pr_safety.git_context._ref_exists", lambda ref: False)

    with pytest.raises(GitContextError, match="base ref does not resolve: feature/base"):
        resolve_base_ref("feature/base")


def test_changed_files_runs_merge_base_diff_and_ignores_blank_lines(monkeypatch):
    def fake_run(args, capture_output, text, check):
        assert args == ["git", "diff", "--name-only", "origin/main...HEAD"]
        assert capture_output is True
        assert text is True
        assert check is False
        return _completed(args, stdout="app/foo.py\n\ntests/test_foo.py\n")

    monkeypatch.setattr("app.pr_safety.git_context.subprocess.run", fake_run)

    assert changed_files("origin/main") == ["app/foo.py", "tests/test_foo.py"]


def test_commits_behind_runs_rev_list_count_and_parses_integer(monkeypatch):
    def fake_run(args, capture_output, text, check):
        assert args == ["git", "rev-list", "--count", "HEAD..origin/main"]
        return _completed(args, stdout="12\n")

    monkeypatch.setattr("app.pr_safety.git_context.subprocess.run", fake_run)

    assert commits_behind("origin/main") == 12


def test_head_commit_message_reads_subject_and_body_separately(monkeypatch):
    seen: list[list[str]] = []

    def fake_run(args, capture_output, text, check):
        seen.append(args)
        if args[-1] == "--pretty=%s":
            return _completed(args, stdout="Add foo\n")
        if args[-1] == "--pretty=%b":
            return _completed(args, stdout="Body text\n\nMore detail\n")
        raise AssertionError(f"unexpected args: {args}")

    monkeypatch.setattr("app.pr_safety.git_context.subprocess.run", fake_run)

    assert head_commit_message() == ("Add foo", "Body text\n\nMore detail")
    assert seen == [
        ["git", "log", "-1", "--pretty=%s"],
        ["git", "log", "-1", "--pretty=%b"],
    ]


def test_run_git_raises_descriptive_error_with_stderr(monkeypatch):
    def fake_run(args, capture_output, text, check):
        return _completed(args, stderr="bad revision", returncode=128)

    monkeypatch.setattr("app.pr_safety.git_context.subprocess.run", fake_run)

    with pytest.raises(GitContextError, match="git diff --name-only main...HEAD failed: bad revision"):
        _run_git(["diff", "--name-only", "main...HEAD"])
