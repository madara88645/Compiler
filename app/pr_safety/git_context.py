"""Pure, testable git inspection helpers for PR Safety.

Uses stdlib :mod:`subprocess` only (never ``shell=True``). Each helper shells
out to a single git plumbing command and returns plain Python values. No
network access, no GitHub API — only the local repository state.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CANDIDATE_BASE_REFS = ("origin/main", "origin/master", "main", "master")

# Fail fast instead of hanging: cap every git call, and never let git block on
# an interactive credential prompt (e.g. a ref that triggers an authenticated
# fetch). Windows runners decode with the ANSI codepage under ``text=True``, so
# force UTF-8 with lossy replacement to avoid UnicodeDecodeError on odd bytes.
_GIT_TIMEOUT_SECONDS = 30
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


class GitContextError(RuntimeError):
    """Raised when the local git state cannot answer a PR Safety query."""


def repository_root(cwd: Path | None = None) -> Path:
    """Return the absolute root of the current local git checkout."""
    args = ["rev-parse", "--show-toplevel"]
    if cwd is not None:
        args = ["-C", str(cwd), *args]
    output = _run_git(args)
    root = Path(output)
    if not root.is_absolute():
        root = (cwd or Path.cwd()) / root
    return root.resolve()


def _run_git(args: list[str]) -> str:
    """Run ``git <args>`` and return stripped stdout, raising on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_GIT_ENV,
            check=False,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitContextError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitContextError(
            f"git {' '.join(args)} timed out after {_GIT_TIMEOUT_SECONDS}s"
        ) from exc

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise GitContextError(f"git {' '.join(args)} failed: {message}")

    return result.stdout.strip()


def _ref_exists(ref: str) -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_GIT_ENV,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitContextError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitContextError(
            f"git rev-parse {ref} timed out after {_GIT_TIMEOUT_SECONDS}s"
        ) from exc
    except subprocess.CalledProcessError:
        return False
    return True


def resolve_base_ref(base: str | None) -> str:
    """Resolve the base ref to diff against.

    If ``base`` is given it must resolve; otherwise the first of
    ``origin/main, origin/master, main, master`` that exists is returned.
    """
    if base:
        if not _ref_exists(base):
            raise GitContextError(f"base ref does not resolve: {base}")
        return base

    for candidate in _CANDIDATE_BASE_REFS:
        if _ref_exists(candidate):
            return candidate

    raise GitContextError(
        "could not resolve a base ref (tried: " + ", ".join(_CANDIDATE_BASE_REFS) + ")"
    )


def changed_files(base: str) -> list[str]:
    """Return files changed between ``base`` and HEAD (merge-base diff)."""
    output = _run_git(["diff", "--name-only", f"{base}...HEAD"])
    return [line for line in output.splitlines() if line.strip()]


def commits_behind(base: str) -> int:
    """Return how many commits HEAD is behind ``base``."""
    output = _run_git(["rev-list", "--count", f"HEAD..{base}"])
    try:
        return int(output)
    except ValueError as exc:
        raise GitContextError(f"unexpected rev-list output: {output!r}") from exc


def head_commit_message() -> tuple[str, str]:
    """Return ``(subject, body)`` of the HEAD commit."""
    subject = _run_git(["log", "-1", "--pretty=%s"])
    body = _run_git(["log", "-1", "--pretty=%b"])
    return subject, body
