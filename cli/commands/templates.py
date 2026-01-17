import typer
from app.templates_manager import get_templates_manager

app = typer.Typer(help="Template management")


@app.command("list")
def template_list(
    filter_role: str = typer.Option(None, "--role", help="Filter by role"),
    filter_tag: str = typer.Option(None, "--tag", help="Filter by tag"),
):
    """List available templates."""
    mgr = get_templates_manager()
    templates = mgr.list_templates(role=filter_role, tag=filter_tag)

    if not templates:
        typer.echo("No templates found.")
        return

    typer.echo(f"Found {len(templates)} templates:")
    for t in templates:
        tags = f" [{', '.join(t.get('tags', []))}]" if t.get("tags") else ""
        typer.echo(
            f"  - {t['id']} ({t.get('role', 'unknown')}){tags}: {t.get('description', 'No description')}"
        )


@app.command("show")
def template_show(
    template_id: str = typer.Argument(..., help="Template ID"),
):
    """Show details of a template."""
    mgr = get_templates_manager()
    tmpl = mgr.get_template(template_id)
    if not tmpl:
        typer.echo(f"Template '{template_id}' not found.")
        raise typer.Exit(1)

    typer.echo(f"Template: {tmpl['id']}")
    typer.echo(f"Role: {tmpl.get('role', 'N/A')}")
    typer.echo(f"Description: {tmpl.get('description', 'N/A')}")
    typer.echo("---")
    typer.echo(tmpl.get("content", ""))
