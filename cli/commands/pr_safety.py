"""PR Safety command: ``pr-safety``.

Exposes the existing offline PR Safety analyzer (``app/pr_safety``) on the CLI.
Fully offline and deterministic — no network, GitHub, or AI calls. The optional
``--from-git`` mode reads the *local* repository state via stdlib subprocess.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer

from app.pr_safety.analyzer import analyze_pr_safety
from app.pr_safety.git_context import (
    GitContextError,
    changed_files as git_changed_files,
    commits_behind as git_commits_behind,
    head_commit_message,
    repository_root,
    resolve_base_ref,
)
from app.pr_safety.markdown import report_to_markdown
from app.pr_safety.repo_signals import collect_repo_signals

from cli.commands._base import app
from cli.commands._helpers import _write_output
from cli.render import get_console, render_pr_safety_report

_VALID_FORMATS = {"human", "json", "md"}


def _read_files_from(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise typer.BadParameter(f"Cannot read --files-from file: {path} ({exc})")
    return [line.strip() for line in text.splitlines() if line.strip()]


@app.command("pr-safety")
def pr_safety_command(
    files: List[str] = typer.Argument(
        None, help="Changed file paths (positional)", show_default=False
    ),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="PR title"),
    description: Optional[str] = typer.Option(None, "--description", help="PR description / body"),
    files_from: Optional[Path] = typer.Option(
        None, "--files-from", help="Read changed files from a newline-delimited file"
    ),
    from_git: bool = typer.Option(
        False, "--from-git", help="Derive changed files and freshness from local git state"
    ),
    base: Optional[str] = typer.Option(
        None, "--base", help="Base ref for --from-git (default: origin/main, main, ...)"
    ),
    commits_behind: Optional[int] = typer.Option(
        None, "--commits-behind", help="Commits behind base (branch freshness signal)"
    ),
    fmt: str = typer.Option(
        "human", "--format", "-f", help="Output format: human|json|md (default: human)"
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to a file"),
    exit_code: bool = typer.Option(
        False, "--exit-code", help="Exit non-zero when the verdict is not 'merge'"
    ),
):
    """Analyze a PR for merge safety using offline heuristics."""
    fmt_l = (fmt or "human").lower()
    if fmt_l not in _VALID_FORMATS:
        raise typer.BadParameter("Unknown --format. Use human|json|md")

    resolved_files: List[str]
    repo_signals = None

    if from_git:
        try:
            base_ref = resolve_base_ref(base)
            resolved_files = git_changed_files(base_ref)
            if commits_behind is None:
                commits_behind = git_commits_behind(base_ref)
            git_subject, git_body = head_commit_message()
            repo_signals = collect_repo_signals(repository_root(), resolved_files)
        except GitContextError as exc:
            typer.secho(f"git error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        if title is None:
            title = git_subject
        if description is None:
            description = git_body
    else:
        if files_from is not None:
            resolved_files = _read_files_from(files_from)
        elif files:
            resolved_files = list(files)
        elif not sys.stdin.isatty():
            resolved_files = [
                line.strip() for line in sys.stdin.read().splitlines() if line.strip()
            ]
        else:
            resolved_files = []

        if title is None:
            raise typer.BadParameter("Provide --title (or use --from-git)")
        if description is None:
            raise typer.BadParameter("Provide --description (or use --from-git)")

    report = analyze_pr_safety(
        title=title,
        description=description,
        changed_files=resolved_files,
        commits_behind=commits_behind,
        repo_signals=repo_signals,
    )

    if fmt_l == "human":
        console = get_console()
        render_pr_safety_report(console, report)
    elif fmt_l == "json":
        payload = json.dumps(report.model_dump(), indent=2)
        _write_output(payload, out, None, default_name="pr_safety.json")
    else:  # md
        payload = report_to_markdown(report)
        _write_output(payload, out, None, default_name="pr_safety.md")

    if exit_code and report.verdict != "merge":
        raise typer.Exit(code=1)
