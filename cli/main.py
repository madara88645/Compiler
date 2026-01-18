from __future__ import annotations
from cli.commands.core import app as core_app
from cli.commands.rag import app as rag_app
from cli.commands.templates import app as templates_app
from cli.commands.analytics import analytics_app, history_app
from cli.commands.tui import app as tui_app
from cli.commands.testing import app as testing_app
from cli.commands.optimize import app as optimize_app

# Import legacy apps from the renamed file
from cli.commands.utils import (
    plugins_app,
    profiles_app,
    export_app,
)
from cli.commands.resources import (
    favorites_app,
    snippets_app,
    collections_app,
    palette_app,
)

# Main entry point uses core commands
app = core_app

# Mount refactored modules
app.add_typer(rag_app, name="rag")
app.add_typer(templates_app, name="template")
app.add_typer(analytics_app, name="analytics")
app.add_typer(history_app, name="history")
app.add_typer(testing_app, name="test")
app.add_typer(optimize_app, name="optimize")
app.add_typer(tui_app)  # tui command is "tui" inside this app

# Mount legacy modules
app.add_typer(plugins_app, name="plugins")
app.add_typer(export_app, name="export")
app.add_typer(favorites_app, name="favorites")
app.add_typer(snippets_app, name="snippets")
app.add_typer(collections_app, name="collections")
app.add_typer(palette_app, name="palette")
app.add_typer(profiles_app, name="profile")

if __name__ == "__main__":
    app()
