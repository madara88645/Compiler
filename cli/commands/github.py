from __future__ import annotations

from pathlib import Path
from typing import List, Literal

import typer

from app.github_artifacts import render_github_artifact


app = typer.Typer(help="GitHub artifact helpers")


@app.command("render")
def render(
    text: List[str] = typer.Argument(None, help="Intent text to render", show_default=False),
    type: Literal["issue-brief", "implementation-checklist", "pr-review-brief"] = typer.Option(
        "issue-brief", "--type", help="Artifact kind to render"
    ),
    from_file: Path = typer.Option(None, "--from-file", help="Read the source text from a file"),
):
    """Render a GitHub-friendly markdown artifact from natural language intent."""
    if from_file is not None:
        try:
            source_text = from_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise typer.BadParameter(f"Could not read from file '{from_file}': {exc}") from exc
    else:
        source_text = " ".join(text or [])

    if not source_text.strip():
        raise typer.BadParameter("Provide TEXT or --from-file")

    typer.echo(render_github_artifact(type, source_text))
