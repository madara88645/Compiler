"""Tests for PR Safety git-context helpers (``app/pr_safety/git_context``)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import app.pr_safety.git_context as git_context_mod
from app.pr_safety.git_context import (
    GitContextError,
    changed_files,
    commits_behind,
    head_commit_message,
    resolve_base_ref,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path, *, branch: str = "main") -> None:
    _git(path, "init", "-b", branch)
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")


def _commit_all(path: Path, message: str) -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-m", message)


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal repo with one commit on ``main``."""
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("initial\n")
    _commit_all(tmp_path, "initial commit")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_resolve_base_ref_uses_explicit_ref(git_repo: Path) -> None:
    assert resolve_base_ref("main") == "main"


def test_resolve_base_ref_rejects_missing_explicit_ref(git_repo: Path) -> None:
    with pytest.raises(GitContextError, match="base ref does not resolve"):
        resolve_base_ref("does-not-exist")


def test_resolve_base_ref_picks_first_candidate(git_repo: Path) -> None:
    assert resolve_base_ref(None) == "main"


def test_resolve_base_ref_errors_when_no_candidate_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path, branch="feature")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(GitContextError, match="could not resolve a base ref"):
        resolve_base_ref(None)


def test_changed_files_lists_files_on_feature_branch(git_repo: Path) -> None:
    _git(git_repo, "checkout", "-b", "feature")
    (git_repo / "app.py").write_text("print('hi')\n")
    _commit_all(git_repo, "add app")

    assert changed_files("main") == ["app.py"]


def test_commits_behind_counts_commits_on_base_not_in_head(git_repo: Path) -> None:
    _git(git_repo, "checkout", "-b", "feature")
    _git(git_repo, "checkout", "main")
    (git_repo / "main-only.txt").write_text("ahead\n")
    _commit_all(git_repo, "advance main")
    _git(git_repo, "checkout", "feature")

    assert commits_behind("main") == 1


def test_head_commit_message_returns_subject_and_body(git_repo: Path) -> None:
    (git_repo / "note.txt").write_text("body line\n")
    _commit_all(git_repo, "subject line\n\nbody paragraph")

    subject, body = head_commit_message()
    assert subject == "subject line"
    assert "body paragraph" in body


def test_git_missing_raises_git_context_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _missing)
    with pytest.raises(GitContextError, match="git executable not found"):
        resolve_base_ref("main")


def test_commits_behind_rejects_non_integer_output(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(git_context_mod, "_run_git", lambda _args: "not-a-number")
    with pytest.raises(GitContextError, match="unexpected rev-list output"):
        commits_behind("main")


def test_changed_files_passes_hardened_subprocess_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="app.py\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    assert changed_files("main") == ["app.py"]

    cmd, kwargs = calls[0]
    assert cmd == ["git", "diff", "--name-only", "main...HEAD"]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["timeout"] == git_context_mod._GIT_TIMEOUT_SECONDS
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert kwargs["check"] is False


def test_resolve_base_ref_passes_hardened_subprocess_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    assert resolve_base_ref("main") == "main"

    cmd, kwargs = calls[0]
    assert cmd == ["git", "rev-parse", "--verify", "--quiet", "main^{commit}"]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["timeout"] == git_context_mod._GIT_TIMEOUT_SECONDS
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert kwargs["check"] is True


def test_changed_files_timeout_raises_git_context_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _timeout(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=git_context_mod._GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", _timeout)

    with pytest.raises(
        GitContextError,
        match=r"git diff --name-only main\.\.\.HEAD timed out after 30s",
    ):
        changed_files("main")


def test_resolve_base_ref_timeout_raises_git_context_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _timeout(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=git_context_mod._GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", _timeout)

    with pytest.raises(GitContextError, match=r"git rev-parse main timed out after 30s"):
        resolve_base_ref("main")


def test_changed_files_surfaces_git_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failure(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="fatal: bad revision 'main...HEAD'",
        )

    monkeypatch.setattr(subprocess, "run", _failure)

    with pytest.raises(
        GitContextError,
        match=r"git diff --name-only main\.\.\.HEAD failed: fatal: bad revision",
    ):
        changed_files("main")


def test_changed_files_empty_when_branch_matches_base(git_repo: Path) -> None:
    _git(git_repo, "checkout", "-b", "feature")
    assert changed_files("main") == []


def test_commits_behind_zero_when_up_to_date(git_repo: Path) -> None:
    _git(git_repo, "checkout", "-b", "feature")
    assert commits_behind("main") == 0


def test_head_commit_message_handles_subject_only_commit(git_repo: Path) -> None:
    subject, body = head_commit_message()
    assert subject == "initial commit"
    assert body == ""
