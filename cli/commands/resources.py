import typer
from rich.console import Console

console = Console()

favorites_app = typer.Typer(help="Favorite prompts and bookmarks (DEPRECATED)")
snippets_app = typer.Typer(help="Quick reusable prompt snippets (DEPRECATED)")
collections_app = typer.Typer(help="Collections/workspaces for organizing prompts (DEPRECATED)")
palette_app = typer.Typer(help="Command palette favorites and metadata (DEPRECATED)")


@favorites_app.callback(invoke_without_command=True)
def favorites_main(ctx: typer.Context):
    """Favorites feature has been deprecated and removed."""
    console.print("[yellow]Favorites feature has been deprecated and removed.[/yellow]")


@snippets_app.callback(invoke_without_command=True)
def snippets_main(ctx: typer.Context):
    """Snippets feature has been deprecated and removed."""
    console.print("[yellow]Snippets feature has been deprecated and removed.[/yellow]")


@collections_app.callback(invoke_without_command=True)
def collections_main(ctx: typer.Context):
    """Collections feature has been deprecated and removed."""
    console.print("[yellow]Collections feature has been deprecated and removed.[/yellow]")


@palette_app.callback(invoke_without_command=True)
def palette_main(ctx: typer.Context):
    """Palette feature has been deprecated and removed."""
    console.print("[yellow]Palette feature has been deprecated and removed.[/yellow]")
