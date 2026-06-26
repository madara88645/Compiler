"""Pure, testable git inspection helpers for PR Safety.

Uses stdlib :mod:`subprocess` only (never ``shell=True``). Each helper shells
out to a single git plumbing command and returns plain Python values. No
network access, no GitHub API — only the local repository state.
"""

from __future__ import annotations

import subprocess

_CANDIDATE_BASE_REFS = ("origin/main", "origin/master", "main", "master")


class GitContextError(RuntimeError):
    """Raised when the local git state cannot answer a PR Safety query."""


def _run_git(args: list[str]) -> str:
    """Run ``git <args>`` and return stripped stdout, raising on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitContextError("git executable not found on PATH") from exc

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
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitContextError("git executable not found on PATH") from exc
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
