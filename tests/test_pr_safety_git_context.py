from __future__ import annotations

import subprocess

import pytest

from app.pr_safety import git_context


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_run_git_returns_stripped_stdout(monkeypatch):
    monkeypatch.setattr(
        git_context.subprocess,
        "run",
        lambda *args, **kwargs: _completed(stdout="  app/foo.py\n"),
    )

    assert git_context._run_git(["diff", "--name-only", "main...HEAD"]) == "app/foo.py"


def test_run_git_raises_error_with_stdout_fallback(monkeypatch):
    monkeypatch.setattr(
        git_context.subprocess,
        "run",
        lambda *args, **kwargs: _completed(returncode=1, stdout="unknown revision"),
    )

    with pytest.raises(git_context.GitContextError, match="unknown revision"):
        git_context._run_git(["diff", "--name-only", "main...HEAD"])


def test_run_git_raises_error_when_git_missing(monkeypatch):
    def _missing(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(git_context.subprocess, "run", _missing)

    with pytest.raises(git_context.GitContextError, match="git executable not found"):
        git_context._run_git(["status"])


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (None, True),
        (subprocess.CalledProcessError(1, ["git"]), False),
    ],
)
def test_ref_exists_handles_success_and_missing_refs(monkeypatch, side_effect, expected):
    def _run(*args, **kwargs):
        if side_effect is not None:
            raise side_effect
        return _completed()

    monkeypatch.setattr(git_context.subprocess, "run", _run)

    assert git_context._ref_exists("origin/main") is expected


def test_ref_exists_raises_error_when_git_missing(monkeypatch):
    def _missing(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(git_context.subprocess, "run", _missing)

    with pytest.raises(git_context.GitContextError, match="git executable not found"):
        git_context._ref_exists("origin/main")


def test_resolve_base_ref_checks_candidates_in_priority_order(monkeypatch):
    seen: list[str] = []

    def _exists(ref: str) -> bool:
        seen.append(ref)
        return ref == "main"

    monkeypatch.setattr(git_context, "_ref_exists", _exists)

    assert git_context.resolve_base_ref(None) == "main"
    assert seen == ["origin/main", "origin/master", "main"]


def test_resolve_base_ref_returns_explicit_ref_when_present(monkeypatch):
    seen: list[str] = []

    def _exists(ref: str) -> bool:
        seen.append(ref)
        return ref == "origin/release"

    monkeypatch.setattr(git_context, "_ref_exists", _exists)

    assert git_context.resolve_base_ref("origin/release") == "origin/release"
    assert seen == ["origin/release"]


def test_resolve_base_ref_rejects_unknown_explicit_ref(monkeypatch):
    monkeypatch.setattr(git_context, "_ref_exists", lambda ref: False)

    with pytest.raises(git_context.GitContextError, match="base ref does not resolve"):
        git_context.resolve_base_ref("release/does-not-exist")


def test_resolve_base_ref_raises_when_no_base_candidate_exists(monkeypatch):
    monkeypatch.setattr(git_context, "_ref_exists", lambda ref: False)

    with pytest.raises(git_context.GitContextError, match="could not resolve a base ref"):
        git_context.resolve_base_ref(None)


def test_changed_files_drops_blank_lines(monkeypatch):
    monkeypatch.setattr(
        git_context,
        "_run_git",
        lambda args: "app/foo.py\n\n tests/test_foo.py \n",
    )

    assert git_context.changed_files("origin/main") == ["app/foo.py", " tests/test_foo.py "]


@pytest.mark.parametrize(
    ("output", "expected", "error_match"),
    [
        ("12", 12, None),
        ("not-a-number", None, "unexpected rev-list output"),
    ],
)
def test_commits_behind_parses_expected_values(monkeypatch, output, expected, error_match):
    monkeypatch.setattr(git_context, "_run_git", lambda args: output)

    if error_match is not None:
        with pytest.raises(git_context.GitContextError, match=error_match):
            git_context.commits_behind("origin/main")
    else:
        assert git_context.commits_behind("origin/main") == expected


def test_head_commit_message_reads_subject_and_body(monkeypatch):
    calls: list[list[str]] = []

    def _run(args: list[str]) -> str:
        calls.append(args)
        if args[-1] == "--pretty=%s":
            return "feat: add pr safety"
        return "Body line one\nBody line two"

    monkeypatch.setattr(git_context, "_run_git", _run)

    assert git_context.head_commit_message() == (
        "feat: add pr safety",
        "Body line one\nBody line two",
    )
    assert calls == [
        ["log", "-1", "--pretty=%s"],
        ["log", "-1", "--pretty=%b"],
    ]
