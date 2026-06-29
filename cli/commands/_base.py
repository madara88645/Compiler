"""Shared Typer app instance + CLI meta commands (version)."""

from __future__ import annotations

from typing import Optional

import typer
from rich import print as rich_print
from rich.console import Console

from app import get_version

app = typer.Typer(no_args_is_help=True)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(get_version())
        raise typer.Exit()


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the prcompiler version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """
    prcompiler — turn messy natural-language requests into structured prompts,
    plans, and exportable artifacts.

    Example: promptc compile "write a haiku about the sea"
    """


@app.command()
def version():
    """Print package version."""
    rich_print(get_version())


# Register the standalone export command for lightweight consumers that import
# `cli.commands._base.app` directly rather than the full core command aggregator.
from cli.commands import compile_export as _compile_export  # noqa: E402,F401
