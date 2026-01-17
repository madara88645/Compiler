from __future__ import annotations
import json
import typer
from rich import print
from typing import Optional, List
from pathlib import Path

# Imports from app
from app.favorites import get_favorites_manager
from app.snippets import get_snippets_manager
from app.collections import get_collections_manager
from app.command_palette import (
    get_command_palette_commands,
    get_command_palette_command_map,
    get_saved_palette_favorites,
    get_saved_palette_favorites_list,
    get_ui_config_path,
    backup_ui_config,
    export_palette_favorites,
    load_exported_palette_favorites,
    persist_palette_favorites,
)

favorites_app = typer.Typer(help="Favorite prompts and bookmarks")
snippets_app = typer.Typer(help="Quick reusable prompt snippets")
collections_app = typer.Typer(help="Collections/workspaces for organizing prompts")
palette_app = typer.Typer(help="Command palette favorites and metadata")


# ============================================================================
# Favorites Commands
# ============================================================================


@favorites_app.command("list")
def favorites_list(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List favorite prompts."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Get favorites
    favorites = favorites_mgr.get_all(tags=tag_list, domain=domain)

    if json_output:
        output = [f.to_dict() for f in favorites]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not favorites:
        console.print("[yellow]No favorites found[/yellow]")
        return

    console.print(f"\n[bold cyan]Favorites[/bold cyan] [dim]({len(favorites)} total)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Tags", width=20)
    table.add_column("Uses", justify="right", width=6)
    table.add_column("Prompt", width=40)

    for fav in favorites:
        tags_str = ", ".join(fav.tags[:3]) if fav.tags else "-"
        if len(fav.tags) > 3:
            tags_str += "..."

        table.add_row(
            fav.id,
            f"{fav.score:.1f}",
            fav.domain,
            tags_str,
            str(fav.use_count),
            fav.prompt_text[:37] + "..." if len(fav.prompt_text) > 40 else fav.prompt_text,
        )

    console.print(table)


@favorites_app.command("show")
def favorites_show(favorite_id: str = typer.Argument(..., help="Favorite ID")):
    """
    Show full details of a favorite

    Example:
        promptc favorites show abc123
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    entry = favorites_mgr.get_by_id(favorite_id)

    if not entry:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)

    info = f"""[bold]ID:[/bold] {entry.id}
[bold]Prompt ID:[/bold] {entry.prompt_id}
[bold]Domain:[/bold] {entry.domain}
[bold]Language:[/bold] {entry.language.upper()}
[bold]Score:[/bold] {entry.score:.1f}
[bold]Use Count:[/bold] {entry.use_count}
[bold]Tags:[/bold] {', '.join(entry.tags) if entry.tags else 'none'}
[bold]Added:[/bold] {entry.timestamp}

[bold]Prompt:[/bold]
{entry.prompt_text}

[bold]Notes:[/bold]
{entry.notes if entry.notes else '(no notes)'}"""

    console.print(
        Panel(info, title=f"[bold cyan]Favorite: {entry.id}[/bold cyan]", border_style="cyan")
    )


@favorites_app.command("remove")
def favorites_remove(favorite_id: str = typer.Argument(..., help="Favorite ID to remove")):
    """
    Remove a favorite

    Example:
        promptc favorites remove abc123
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.remove(favorite_id):
        console.print(f"[green]✓ Removed favorite: {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("search")
def favorites_search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Search favorites by text

    Example:
        promptc favorites search "python tutorial"
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    results = favorites_mgr.search(query)

    if json_output:
        output = [f.to_dict() for f in results]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not results:
        console.print(f"[yellow]No favorites found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold cyan]Search Results[/bold cyan] [dim]({len(results)} matches)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Prompt", width=50)

    for fav in results:
        # Highlight query in text
        prompt_display = (
            fav.prompt_text[:47] + "..." if len(fav.prompt_text) > 50 else fav.prompt_text
        )
        table.add_row(fav.id, f"{fav.score:.1f}", fav.domain, prompt_display)

    console.print(table)


@favorites_app.command("tag")
def favorites_tag(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    tag: str = typer.Argument(..., help="Tag to add"),
):
    """
    Add a tag to a favorite

    Example:
        promptc favorites tag abc123 important
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.add_tag(favorite_id, tag):
        console.print(f"[green]✓ Added tag '{tag}' to favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("untag")
def favorites_untag(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    tag: str = typer.Argument(..., help="Tag to remove"),
):
    """
    Remove a tag from a favorite

    Example:
        promptc favorites untag abc123 important
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.remove_tag(favorite_id, tag):
        console.print(f"[green]✓ Removed tag '{tag}' from favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("note")
def favorites_note(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    notes: str = typer.Argument(..., help="Notes text"),
):
    """
    Update notes for a favorite

    Example:
        promptc favorites note abc123 "This is my best prompt for tutorials"
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.update_notes(favorite_id, notes):
        console.print(f"[green]✓ Updated notes for favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("stats")
def favorites_stats():
    """
    Show favorites statistics

    Example:
        promptc favorites stats
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    stats = favorites_mgr.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]No favorites yet[/yellow]")
        return

    info = f"""[bold]Total Favorites:[/bold] {stats['total']}
[bold]Total Uses:[/bold] {stats['total_uses']}
[bold]Avg Score:[/bold] {stats['avg_score']:.1f}

[bold]Top Domains:[/bold]"""

    for domain, count in list(stats["domains"].items())[:5]:
        info += f"\n  {domain}: {count}"

    if stats["tags"]:
        info += "\n\n[bold]Top Tags:[/bold]"
        for tag, count in list(stats["tags"].items())[:10]:
            info += f"\n  {tag}: {count}"

    info += "\n\n[bold]Languages:[/bold]"
    for lang, count in stats["languages"].items():
        info += f"\n  {lang}: {count}"

    console.print(
        Panel(info, title="[bold cyan]Favorites Stats[/bold cyan]", border_style="cyan")
    )


@favorites_app.command("most-used")
def favorites_most_used(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of items to show"),
):
    """
    Show most used favorites

    Example:
        promptc favorites most-used --limit 5
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    most_used = favorites_mgr.get_most_used(limit=limit)

    if not most_used:
        console.print("[yellow]No favorites found[/yellow]")
        return

    table = Table(
        title=f"Top {limit} Most Used Favorites", show_header=True, header_style="bold cyan"
    )
    table.add_column("Rank", style="magenta", width=6)
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Uses", style="green", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Prompt", width=40)

    for rank, fav in enumerate(most_used, 1):
        table.add_row(
            str(rank),
            fav.id,
            str(fav.use_count),
            fav.domain,
            fav.prompt_text[:37] + "..." if len(fav.prompt_text) > 40 else fav.prompt_text,
        )

    console.print(table)


@favorites_app.command("use")
def favorites_use(
    favorite_id: str = typer.Argument(..., help="Favorite ID to use"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy prompt text to clipboard"),
):
    """
    Use a favorite (increments use count and returns text)

    Example:
        promptc favorites use abc123
        promptc favorites use abc123 --copy
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    text = favorites_mgr.use(favorite_id)

    if text is None:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)

    console.print(
        Panel(text, title=f"[bold green]Favorite Used: {favorite_id}[/bold green]", border_style="green")
    )

    if copy:
        try:
            import pyperclip

            pyperclip.copy(text)
            console.print("\n[green]✓ Copied to clipboard[/green]")
        except ImportError:
            console.print("\n[yellow]⚠ pyperclip not installed, skipping clipboard copy[/yellow]")


@favorites_app.command("clear")
def favorites_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Clear all favorites

    Example:
        promptc favorites clear
    """
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    favorites_mgr = get_favorites_manager()

    if not force:
        confirm = Confirm.ask("Are you sure you want to delete ALL favorites?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    favorites_mgr.clear()
    console.print("[green]✓ All favorites cleared[/green]")


# ============================================================================
# Quick Snippets Commands
# ============================================================================


@snippets_app.command("add")
def snippets_add(
    snippet_id: str = typer.Argument(..., help="Unique snippet ID"),
    title: str = typer.Option(..., "--title", "-t", help="Snippet title"),
    content: str = typer.Option(None, "--content", "-c", help="Snippet content"),
    category: str = typer.Option(
        "general", "--category", help="Category (constraint, example, context, etc.)"
    ),
    description: str = typer.Option("", "--description", "-d", help="Optional description"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    language: str = typer.Option("en", "--language", "-l", help="Content language"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read content from file"
    ),
):
    """Add a new snippet."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    try:
        # Get content
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            content = from_file.read_text(encoding="utf-8")
        elif not content:
            console.print("[bold red]✗ Content is required[/bold red]")
            console.print("[dim]Use --content or --from-file[/dim]")
            raise typer.Exit(code=1)

        # Parse tags
        tag_list = [t.strip() for t in tags.split(",")] if tags else []

        # Add snippet
        snippet = manager.add(
            snippet_id=snippet_id,
            title=title,
            content=content,
            category=category,
            description=description,
            tags=tag_list,
            language=language,
        )

        content_preview = content[:100] + "..." if len(content) > 100 else content

        info = f"""[bold]ID:[/bold] {snippet.id}
[bold]Title:[/bold] {snippet.title}
[bold]Category:[/bold] {snippet.category}
[bold]Tags:[/bold] {', '.join(snippet.tags) or 'None'}
[bold]Language:[/bold] {snippet.language}

[bold]Content:[/bold]
{content_preview}"""

        console.print(
            Panel(info, title="[bold green]✓ Snippet Added[/bold green]", border_style="green")
        )

    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]✗ Error adding snippet:[/bold red] {e}")
        raise typer.Exit(code=1)


@snippets_app.command("list")
def snippets_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated)"
    ),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all snippets."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    snippets = manager.get_all(category=category, tags=tag_list, language=language)

    if not snippets:
        console.print("[yellow]No snippets found[/yellow]")
        return

    if json_output:
        output = [s.to_dict() for s in snippets]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    table = Table(title="Snippets", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Tags", style="blue", width=20)
    table.add_column("Uses", style="magenta", width=8)

    for snippet in snippets:
        tags_str = ", ".join(snippet.tags[:2])
        if len(snippet.tags) > 2:
            tags_str += "..."

        table.add_row(
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            tags_str,
            str(snippet.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(snippets)} snippets[/dim]")


@snippets_app.command("show")
def snippets_show(
    snippet_id: str = typer.Argument(..., help="Snippet ID to show"),
):
    """Show full snippet details."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    info = f"""[bold]ID:[/bold] {snippet.id}
[bold]Title:[/bold] {snippet.title}
[bold]Category:[/bold] {snippet.category}
[bold]Description:[/bold] {snippet.description or 'None'}
[bold]Tags:[/bold] {', '.join(snippet.tags) or 'None'}
[bold]Language:[/bold] {snippet.language}
[bold]Use Count:[/bold] {snippet.use_count}
[bold]Created:[/bold] {snippet.created_at.split('T')[0]}
[bold]Last Used:[/bold] {snippet.last_used.split('T')[0] if snippet.last_used else 'Never'}"""

    console.print(
        Panel(info, title="[bold cyan]Snippet Information[/bold cyan]", border_style="cyan")
    )

    console.print("\n[bold yellow]Content:[/bold yellow]")
    syntax = Syntax(snippet.content, "markdown", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, border_style="yellow"))


@snippets_app.command("use")
def snippets_use(
    snippet_id: str = typer.Argument(..., help="Snippet ID to use"),
    copy: bool = typer.Option(False, "--copy", help="Copy to clipboard"),
):
    """Use a snippet (shows content and increments use count)."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    content = manager.use(snippet_id)
    if content is None:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(content, title="[bold green]Snippet Content[/bold green]", border_style="green")
    )

    if copy:
        try:
            import pyperclip

            pyperclip.copy(content)
            console.print("\n[green]✓ Copied to clipboard[/green]")
        except ImportError:
            console.print("\n[yellow]⚠ pyperclip not installed - cannot copy to clipboard[/yellow]")


@snippets_app.command("delete")
def snippets_delete(
    snippet_id: str = typer.Argument(..., help="Snippet ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a snippet."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    if not force:
        confirm = Confirm.ask(f"Delete snippet '{snippet.title}' ({snippet_id})?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    success = manager.delete(snippet_id)
    if success:
        console.print(f"[green]✓ Snippet '{snippet_id}' deleted[/green]")
    else:
        console.print("[bold red]✗ Failed to delete snippet[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("edit")
def snippets_edit(
    snippet_id: str = typer.Argument(..., help="Snippet ID to edit"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="New title"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="New content"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    category: Optional[str] = typer.Option(None, "--category", help="New category"),
    tags: Optional[str] = typer.Option(None, "--tags", help="New comma-separated tags"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read content from file"
    ),
):
    """Edit a snippet."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    try:
        # Get content from file if provided
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            content = from_file.read_text(encoding="utf-8")

        # Parse tags
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]

        # Update snippet
        updated = manager.update(
            snippet_id=snippet_id,
            title=title,
            content=content,
            description=description,
            category=category,
            tags=tag_list,
        )

        if updated:
            info = f"""[bold]ID:[/bold] {updated.id}
[bold]Title:[/bold] {updated.title}
[bold]Category:[/bold] {updated.category}
[bold]Tags:[/bold] {', '.join(updated.tags) or 'None'}"""

            console.print(
                Panel(
                    info, title="[bold green]✓ Snippet Updated[/bold green]", border_style="green"
                )
            )
        else:
            console.print("[bold red]✗ Failed to update snippet[/bold red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]✗ Error updating snippet:[/bold red] {e}")
        raise typer.Exit(code=1)


@snippets_app.command("search")
def snippets_search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search snippets by query."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    results = manager.search(query)

    if not results:
        console.print(f"[yellow]No snippets found matching '{query}'[/yellow]")
        return

    if json_output:
        output = [s.to_dict() for s in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    table = Table(title=f"Search Results for '{query}'", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Uses", style="magenta", width=8)

    for snippet in results:
        table.add_row(
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            str(snippet.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Found: {len(results)} snippets[/dim]")


@snippets_app.command("categories")
def snippets_categories():
    """List all snippet categories."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    categories = manager.get_categories()

    if not categories:
        console.print("[yellow]No categories found[/yellow]")
        return

    table = Table(title="Snippet Categories", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Snippets", style="green")

    for category in categories:
        snippets = manager.get_all(category=category)
        table.add_row(category, str(len(snippets)))

    console.print(table)


@snippets_app.command("tag")
def snippets_tag(
    snippet_id: str = typer.Argument(..., help="Snippet ID"),
    tag: str = typer.Argument(..., help="Tag to add"),
):
    """Add a tag to a snippet."""
    from rich.console import Console

    console = Console()
    manager = get_snippets_manager()

    success = manager.add_tag(snippet_id, tag)
    if success:
        console.print(f"[green]✓ Tag '{tag}' added to snippet '{snippet_id}'[/green]")
    else:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("untag")
def snippets_untag(
    snippet_id: str = typer.Argument(..., help="Snippet ID"),
    tag: str = typer.Argument(..., help="Tag to remove"),
):
    """Remove a tag from a snippet."""
    from rich.console import Console

    console = Console()
    manager = get_snippets_manager()

    success = manager.remove_tag(snippet_id, tag)
    if success:
        console.print(f"[green]✓ Tag '{tag}' removed from snippet '{snippet_id}'[/green]")
    else:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found or tag not present[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("stats")
def snippets_stats():
    """Show snippet statistics."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    stats = manager.get_stats()

    info = f"""[bold]Total Snippets:[/bold] {stats['total_snippets']}
[bold]Total Uses:[/bold] {stats['total_uses']}"""

    console.print(
        Panel(info, title="[bold cyan]Snippet Statistics[/bold cyan]", border_style="cyan")
    )

    # Categories
    if stats["categories"]:
        console.print("\n[bold yellow]By Category:[/bold yellow]")
        for category, count in sorted(stats["categories"].items()):
            console.print(f"  [cyan]{category}:[/cyan] {count}")

    # Languages
    if stats["languages"]:
        console.print("\n[bold yellow]By Language:[/bold yellow]")
        for language, count in sorted(stats["languages"].items()):
            console.print(f"  [cyan]{language}:[/cyan] {count}")

    # Most used
    if stats["most_used"]:
        table = Table(title="Most Used Snippets", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Uses", style="magenta")

        for item in stats["most_used"]:
            table.add_row(
                item["id"],
                item["title"],
                item["category"],
                str(item["use_count"]),
            )

        console.print("\n")
        console.print(table)


@snippets_app.command("most-used")
def snippets_most_used(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of snippets to show"),
):
    """Show most used snippets."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    most_used = manager.get_most_used(limit=limit)

    if not most_used:
        console.print("[yellow]No snippets found[/yellow]")
        return

    table = Table(
        title=f"Top {limit} Most Used Snippets", show_header=True, header_style="bold cyan"
    )
    table.add_column("Rank", style="magenta", width=6)
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Uses", style="magenta", width=8)

    for rank, snippet in enumerate(most_used, 1):
        table.add_row(
            str(rank),
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            str(snippet.use_count),
        )

    console.print(table)


@snippets_app.command("clear")
def snippets_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all snippets."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()

    if not force:
        confirm = Confirm.ask("Are you sure you want to delete ALL snippets?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    manager = get_snippets_manager()
    manager.clear()
    console.print("[green]✓ All snippets cleared[/green]")


# ============================================================
# Collections / Workspaces Commands
# ============================================================


@collections_app.command("create")
def collections_create(
    collection_id: str = typer.Argument(..., help="Unique collection ID"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    tags: List[str] = typer.Option(
        None, "--tag", "-t", help="Tags (can be specified multiple times)"
    ),
    color: str = typer.Option("blue", "--color", "-c", help="Color for UI display"),
    set_active: bool = typer.Option(False, "--active", "-a", help="Set as active collection"),
):
    """Create a new collection/workspace."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.create(
            collection_id=collection_id,
            name=name,
            description=description,
            tags=tags or [],
            color=color,
        )

        if set_active:
            collections_mgr.set_active_collection(collection_id)

        console.print(
            Panel(
                f"[bold green]Collection Created[/bold green]\n\n"
                f"[cyan]ID:[/cyan] {collection.id}\n"
                f"[cyan]Name:[/cyan] {collection.name}\n"
                f"[cyan]Description:[/cyan] {collection.description or '(none)'}\n"
                f"[cyan]Tags:[/cyan] {', '.join(collection.tags) if collection.tags else '(none)'}\n"
                f"[cyan]Color:[/cyan] {collection.color}\n"
                f"[cyan]Active:[/cyan] {'Yes' if set_active else 'No'}",
                title="✓ Success",
                border_style="green",
            )
        )

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("list")
def collections_list(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    archived: Optional[bool] = typer.Option(
        None, "--archived", "-a", help="Filter by archived status"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all collections."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    collections_mgr = get_collections_manager()

    collections = collections_mgr.get_all(tag=tag, archived=archived)

    if json_output:
        data = [c.to_dict() for c in collections]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not collections:
        console.print("[yellow]No collections found[/yellow]")
        return

    active_id = collections_mgr.get_active_collection()

    table = Table(title="Collections", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Items", justify="right")
    table.add_column("Tags")
    table.add_column("Status")
    table.add_column("Used", justify="right")

    for collection in collections:
        total_items = len(collection.prompts) + len(collection.templates) + len(collection.snippets)

        status_parts = []
        if collection.id == active_id:
            status_parts.append("[bold green]●Active[/bold green]")
        if collection.is_archived:
            status_parts.append("[dim]Archived[/dim]")

        status = " ".join(status_parts) if status_parts else ""

        table.add_row(
            collection.id,
            collection.name,
            str(total_items),
            ", ".join(collection.tags) if collection.tags else "",
            status,
            str(collection.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(collections)} collections[/dim]")


@collections_app.command("show")
def collections_show(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details of a collection."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    collections_mgr = get_collections_manager()

    collection = collections_mgr.get(collection_id)
    if not collection:
        console.print(f"[red]Collection '{collection_id}' not found[/red]")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(collection.to_dict(), indent=2, ensure_ascii=False))
        return

    active_id = collections_mgr.get_active_collection()
    is_active = collection.id == active_id

    # Overview panel
    overview = (
        f"[cyan]Name:[/cyan] {collection.name}\n"
        f"[cyan]ID:[/cyan] {collection.id}\n"
        f"[cyan]Description:[/cyan] {collection.description or '(none)'}\n"
        f"[cyan]Tags:[/cyan] {', '.join(collection.tags) if collection.tags else '(none)'}\n"
        f"[cyan]Color:[/cyan] {collection.color}\n"
        f"[cyan]Created:[/cyan] {collection.created_at}\n"
        f"[cyan]Updated:[/cyan] {collection.updated_at}\n"
        f"[cyan]Use Count:[/cyan] {collection.use_count}\n"
        f"[cyan]Active:[/cyan] {'[bold green]Yes[/bold green]' if is_active else 'No'}\n"
        f"[cyan]Archived:[/cyan] {'Yes' if collection.is_archived else 'No'}"
    )

    console.print(Panel(overview, title=f"Collection: {collection.name}", border_style="cyan"))

    # Items table
    table = Table(title="Items", show_header=True, header_style="bold cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Count", justify="right", style="green")
    table.add_column("IDs", style="dim")

    table.add_row(
        "Prompts",
        str(len(collection.prompts)),
        ", ".join(collection.prompts[:3]) + ("..." if len(collection.prompts) > 3 else ""),
    )
    table.add_row(
        "Templates",
        str(len(collection.templates)),
        ", ".join(collection.templates[:3]) + ("..." if len(collection.templates) > 3 else ""),
    )
    table.add_row(
        "Snippets",
        str(len(collection.snippets)),
        ", ".join(collection.snippets[:3]) + ("..." if len(collection.snippets) > 3 else ""),
    )

    console.print(table)


@collections_app.command("switch")
def collections_switch(
    collection_id: Optional[str] = typer.Argument(
        None, help="Collection ID (omit to clear active)"
    ),
):
    """Switch to a collection (set as active)."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        if collection_id is None:
            collections_mgr.set_active_collection(None)
            console.print("[green]✓ Active collection cleared[/green]")
        else:
            collections_mgr.set_active_collection(collection_id)
            collection = collections_mgr.get(collection_id)
            console.print(
                f"[green]✓ Switched to collection:[/green] [cyan]{collection.name}[/cyan] ({collection_id})"
            )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-prompt")
def collections_add_prompt(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    prompt_id: str = typer.Argument(..., help="Prompt ID/hash to add"),
):
    """Add a prompt to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_prompt(collection_id, prompt_id)
        console.print(
            f"[green]✓ Added prompt[/green] [yellow]{prompt_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-template")
def collections_add_template(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    template_id: str = typer.Argument(..., help="Template ID to add"),
):
    """Add a template to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_template(collection_id, template_id)
        console.print(
            f"[green]✓ Added template[/green] [yellow]{template_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-snippet")
def collections_add_snippet(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    snippet_id: str = typer.Argument(..., help="Snippet ID to add"),
):
    """Add a snippet to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_snippet(collection_id, snippet_id)
        console.print(
            f"[green]✓ Added snippet[/green] [yellow]{snippet_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-prompt")
def collections_remove_prompt(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    prompt_id: str = typer.Argument(..., help="Prompt ID to remove"),
):
    """Remove a prompt from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_prompt(collection_id, prompt_id)
        console.print(
            f"[green]✓ Removed prompt[/green] [yellow]{prompt_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-template")
def collections_remove_template(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    template_id: str = typer.Argument(..., help="Template ID to remove"),
):
    """Remove a template from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_template(collection_id, template_id)
        console.print(
            f"[green]✓ Removed template[/green] [yellow]{template_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-snippet")
def collections_remove_snippet(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    snippet_id: str = typer.Argument(..., help="Snippet ID to remove"),
):
    """Remove a snippet from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_snippet(collection_id, snippet_id)
        console.print(
            f"[green]✓ Removed snippet[/green] [yellow]{snippet_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("update")
def collections_update(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", "-t", help="New tags (replaces existing)"
    ),
    color: Optional[str] = typer.Option(None, "--color", "-c", help="New color"),
):
    """Update a collection's metadata."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.update(
            collection_id=collection_id,
            name=name,
            description=description,
            tags=tags,
            color=color,
        )
        console.print(f"[green]✓ Updated collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("delete")
def collections_delete(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    collection = collections_mgr.get(collection_id)
    if not collection:
        console.print(f"[red]Collection '{collection_id}' not found[/red]")
        raise typer.Exit(code=1)

    if not force:
        console.print(f"[yellow]Delete collection '{collection.name}' ({collection_id})?[/yellow]")
        confirm = typer.confirm("This cannot be undone.")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    collections_mgr.delete(collection_id)
    console.print(f"[green]✓ Deleted collection:[/green] {collection.name}")


@collections_app.command("archive")
def collections_archive(
    collection_id: str = typer.Argument(..., help="Collection ID"),
):
    """Archive a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.archive(collection_id)
        console.print(f"[green]✓ Archived collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("unarchive")
def collections_unarchive(
    collection_id: str = typer.Argument(..., help="Collection ID"),
):
    """Unarchive a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.unarchive(collection_id)
        console.print(f"[green]✓ Unarchived collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("stats")
def collections_stats():
    """Show collection statistics."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    collections_mgr = get_collections_manager()

    stats = collections_mgr.get_stats()

    # Overview panel
    overview = (
        f"[cyan]Total Collections:[/cyan] {stats['total_collections']}\n"
        f"[cyan]Active Collections:[/cyan] {stats['active_collections']}\n"
        f"[cyan]Archived Collections:[/cyan] {stats['archived_collections']}\n\n"
        f"[cyan]Total Prompts:[/cyan] {stats['total_prompts']}\n"
        f"[cyan]Total Templates:[/cyan] {stats['total_templates']}\n"
        f"[cyan]Total Snippets:[/cyan] {stats['total_snippets']}\n\n"
        f"[cyan]Active Collection:[/cyan] {stats['active_collection'] or '(none)'}"
    )

    console.print(Panel(overview, title="Collection Statistics", border_style="cyan"))

    # Most used table
    if stats["most_used"]:
        table = Table(title="Most Used Collections", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Uses", justify="right", style="yellow")
        table.add_column("Items", justify="right", style="magenta")

        for item in stats["most_used"]:
            table.add_row(item["id"], item["name"], str(item["use_count"]), str(item["items"]))

        console.print(table)


@collections_app.command("export")
def collections_export(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
):
    """Export a collection to JSON."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        data = collections_mgr.export_collection(collection_id)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓ Exported to:[/green] {output}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("import")
def collections_import(
    input_file: Path = typer.Argument(..., help="Input JSON file"),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-o", help="Overwrite if collection exists"
    ),
):
    """Import a collection from JSON."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        raise typer.Exit(code=1)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        collection = collections_mgr.import_collection(data, overwrite=overwrite)
        console.print(
            f"[green]✓ Imported collection:[/green] [cyan]{collection.name}[/cyan] ({collection.id})"
        )

    except (ValueError, json.JSONDecodeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("clear")
def collections_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all collections (DANGER)."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    if not force:
        console.print("[bold red]DANGER: This will delete ALL collections and their items![/bold red]")
        confirm = typer.confirm("Are you really sure?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    collections_mgr.clear()
    console.print("[green]✓ All collections cleared[/green]")


# ============================================================================
# Command Palette Helpers
# ============================================================================


@palette_app.command("commands")
def palette_list_commands(json_output: bool = typer.Option(False, "--json", help="Output as JSON")):
    """List available command palette entries and show favorite status."""

    commands = get_command_palette_commands()
    favorites = get_saved_palette_favorites()

    if json_output:
        payload = [
            {"id": cmd.id, "label": cmd.label, "favorite": cmd.id in favorites} for cmd in commands
        ]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    typer.echo("Command Palette Entries:\n")
    for cmd in commands:
        star = "⭐" if cmd.id in favorites else "  "
        typer.echo(f" {star} {cmd.id:<20} {cmd.label}")
    typer.echo(f"\nConfig file: {get_ui_config_path()}")


@palette_app.command("favorites")
def palette_manage_favorites(
    add: Optional[List[str]] = typer.Option(
        None, "--add", "-a", help="Command ID to add to favorites (repeatable)"
    ),
    remove: Optional[List[str]] = typer.Option(
        None, "--remove", "-r", help="Command ID to remove (repeatable)"
    ),
    clear: bool = typer.Option(False, "--clear", help="Remove all favorites"),
    list_stale: bool = typer.Option(
        False,
        "--list-stale",
        help="List stale favorites (commands no longer available)",
    ),
    prune_stale: bool = typer.Option(
        False,
        "--prune-stale",
        help="Remove favorites whose commands no longer exist",
    ),
    export_path: Optional[Path] = typer.Option(
        None,
        "--export",
        help="Write current favorites to a JSON file (creates directories as needed)",
    ),
    import_path: Optional[Path] = typer.Option(
        None,
        "--import-from",
        help="Read favorites from a JSON export file",
    ),
    replace_import: bool = typer.Option(
        False,
        "--replace",
        help="Replace existing favorites when importing instead of merging",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    reorder: Optional[str] = typer.Option(
        None,
        "--reorder",
        help="Reorder favorites with a comma-separated list of command IDs (others keep their relative order)",
    ),
):
    """View or update command palette favorites stored in the desktop UI config."""

    command_map = get_command_palette_command_map()
    favorites_list = get_saved_palette_favorites_list()
    favorites_set = set(favorites_list)
    original_valid_list = [cid for cid in favorites_list if cid in command_map]
    clear_requested = bool(clear)
    has_other_ops = bool(add or remove or import_path or reorder or prune_stale)
    cleared_any = False
    backup_path: Path | None = None
    export_result_path: Path | None = None
    import_ids: list[str] = []
    import_source: Path | None = None
    import_applied = False
    pruned_any = False
    reordered_ids: list[str] = []

    def ensure_command(cmd_id: str) -> None:
        if cmd_id not in command_map:
            typer.secho(
                f"Unknown command id '{cmd_id}'. Run 'promptc palette commands' to inspect valid IDs.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    if clear_requested:
        if favorites_list:
            favorites_list.clear()
            cleared_any = True
        else:
            cleared_any = False

    if import_path:
        import_source = import_path
        try:
            import_ids = load_exported_palette_favorites(import_path)
        except (OSError, ValueError) as exc:
            typer.secho(f"Failed to import favorites: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        if replace_import:
            favorites_list.clear()
            favorites_set.clear()

        for cmd_id in import_ids:
            if cmd_id not in command_map:
                typer.secho(
                    f"Ignoring unknown command id '{cmd_id}' from import.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                continue
            if cmd_id not in favorites_set:
                favorites_list.append(cmd_id)
                favorites_set.add(cmd_id)
                import_applied = True

    for cmd_id in add or []:
        ensure_command(cmd_id)
        if cmd_id not in favorites_set:
            favorites_list.append(cmd_id)
            favorites_set.add(cmd_id)

    for cmd_id in remove or []:
        if cmd_id not in command_map:
            typer.secho(f"Unknown command id '{cmd_id}' ignored.", fg=typer.colors.YELLOW, err=True)
            continue
        if cmd_id in favorites_set:
            favorites_set.remove(cmd_id)
            try:
                favorites_list.remove(cmd_id)
            except ValueError:
                pass

    stale_ids = [cid for cid in favorites_list if cid not in command_map]

    if reorder:
        requested_order = [cid.strip() for cid in reorder.split(",") if cid.strip()]
        reordered_ids = []
        seen: set[str] = set()
        for cid in requested_order:
            if cid not in favorites_set:
                typer.secho(
                    f"Ignoring unknown or non-favorite id '{cid}' in reorder list.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                continue
            if cid in seen:
                continue
            reordered_ids.append(cid)
            seen.add(cid)
        for cid in favorites_list:
            if cid in seen:
                continue
            reordered_ids.append(cid)
            seen.add(cid)
        favorites_list = reordered_ids

    if prune_stale and stale_ids:
        favorites_list = [cid for cid in favorites_list if cid in command_map]
        favorites_set = set(favorites_list)
        pruned_any = True

    valid_favorites_list = [cid for cid in favorites_list if cid in command_map]
    original_valid_sorted = original_valid_list
    new_valid_sorted = valid_favorites_list
    changed = original_valid_sorted != new_valid_sorted

    if changed:
        backup_path = backup_ui_config()
        persist_palette_favorites(valid_favorites_list)

    ordered_commands = [command_map[cid] for cid in valid_favorites_list]

    clear_only_no_effect = clear_requested and not has_other_ops and not cleared_any

    if export_path:
        try:
            export_palette_favorites(export_path, [cmd.id for cmd in ordered_commands])
            export_result_path = export_path
        except OSError as exc:
            typer.secho(f"Failed to export favorites: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    if json_output:
        payload = {
            "favorites": [{"id": cmd.id, "label": cmd.label} for cmd in ordered_commands],
            "config_path": str(get_ui_config_path()),
            "changed": changed,
            "cleared_any": cleared_any,
            "stale_ids": stale_ids,
            "backup_path": str(backup_path) if backup_path else None,
            "export_path": str(export_result_path) if export_result_path else None,
            "import_source": str(import_source) if import_source else None,
            "imported_ids": import_ids,
            "import_replaced": replace_import,
            "pruned_stale": pruned_any,
            "reordered_ids": reordered_ids,
            "favorites_order": [cmd.id for cmd in ordered_commands],
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        if clear_only_no_effect:
            raise typer.Exit(code=1)
        if list_stale and stale_ids:
            raise typer.Exit(code=1)
        return

    if clear_only_no_effect:
        typer.echo("No favorites to clear.")
        raise typer.Exit(code=1)

    if list_stale:
        if stale_ids:
            typer.echo("Stale favorites (not in current command set):")
            for sid in stale_ids:
                typer.echo(f" - {sid}")
        else:
            typer.echo("No stale favorites found.")
