import typer
from typing import Optional
from pathlib import Path
from app.tui import SearchApp

app = typer.Typer(help="TUI")


@app.command("tui")
def tui_launch(
    path: Optional[Path] = typer.Argument(None, help="Initial path to open"),
):
    """Launch the Terminal User Interface."""
    tui_app = SearchApp()
    tui_app.run()
