"""Shared CLI output helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer


def _write_output(
    content: str, out: Optional[Path], out_dir: Optional[Path], default_name: str = "output.txt"
):
    """Helper to write output to file or directory."""
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / default_name
        target.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {target}")
    elif out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {out}")
    else:
        typer.echo(content)
