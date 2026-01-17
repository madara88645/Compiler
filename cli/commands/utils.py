from __future__ import annotations
import json
import typer
from rich import print
from typing import Optional
from pathlib import Path
from datetime import datetime

# Optional YAML support
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

# Imports from app
from app.plugins import describe_plugins
from app.settings_profiles import (
    delete_profile as delete_settings_profile,
    duplicate_active_profile,
    export_profile_to_path,
    get_profile as get_settings_profile,
    import_profile_from_path,
    load_profiles_snapshot,
    rename_profile as rename_settings_profile,
    set_active_profile as set_active_settings_profile,
    snapshot_current_settings_as_profile,
)
from app.export_import import get_export_import_manager

plugins_app = typer.Typer(help="Plugin utilities")
profiles_app = typer.Typer(help="Settings profiles shared with the desktop UI")
export_app = typer.Typer(help="Export and import data")

_PROFILE_SNAPSHOT_KEYS = [
    "diagnostics",
    "trace",
    "use_expanded",
    "render_v2_emitters",
    "only_live_debug",
    "wrap",
    "auto_generate_example",
    "min_priority",
    "model",
    "llm_provider",
    "local_endpoint",
    "local_api_key",
    "user_level",
    "task_type",
    "rag_db_path",
    "rag_embed_dim",
    "rag_method",
    "optimize_max_chars",
    "optimize_max_tokens",
]

# --- PLUGINS ---


@plugins_app.command("list")
def plugins_list(
    refresh: bool = typer.Option(False, "--refresh", help="Reload plugin entry points"),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output"),
):
    """List installed Prompt Compiler plugins."""

    info = describe_plugins(refresh=refresh)
    if json_out:
        typer.echo(json.dumps(info, ensure_ascii=False, indent=2))
        return
    if not info:
        typer.echo(
            "No plugins discovered. Install packages exposing the 'promptc.plugins' entry point"
            " or set PROMPTC_PLUGIN_PATH."
        )
        return
    for item in info:
        line = item["name"]
        if item.get("version"):
            line += f" v{item['version']}"
        if item.get("description"):
            line += f" - {item['description']}"
        provides = item.get("provides") or []
        if provides:
            line += " (" + ", ".join(provides) + ")"
        typer.echo(line)


# --- PROFILES ---


@profiles_app.command("list")
def profile_list(json_output: bool = typer.Option(False, "--json", help="Output JSON")):
    """List available settings profiles."""

    snap = load_profiles_snapshot()
    names = sorted(snap.profiles.keys(), key=lambda s: s.lower())

    if json_output:
        print(json.dumps({"active": snap.active, "profiles": names}, ensure_ascii=False, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Settings Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Active", style="green")
    if not names:
        console.print("(No profiles yet)")
        return
    for name in names:
        table.add_row(name, "✓" if snap.active == name else "")
    console.print(table)


@profiles_app.command("show")
def profile_show(
    name: str = typer.Argument(..., help="Profile name"),
):
    """Show a profile payload as JSON."""

    profile = get_settings_profile(name)
    if not profile:
        raise typer.Exit(code=1)
    print(json.dumps(profile, ensure_ascii=False, indent=2))


@profiles_app.command("save")
def profile_save(
    name: str = typer.Argument(..., help="Profile name"),
    from_active: bool = typer.Option(
        False, "--from-active", help="Duplicate the currently active profile"
    ),
):
    """Save a new profile.

    By default, snapshots the current UI config settings (last saved UI state).
    """

    cleaned = (name or "").strip()
    if not cleaned:
        raise typer.Exit(code=1)

    if from_active:
        try:
            duplicate_active_profile(cleaned)
            return
        except Exception:
            raise typer.Exit(code=1)

    snapshot_current_settings_as_profile(cleaned, _PROFILE_SNAPSHOT_KEYS)


@profiles_app.command("activate")
def profile_activate(
    name: str = typer.Argument(..., help="Profile name to set as active"),
):
    """Set the active profile (the desktop UI will load it on startup)."""

    try:
        set_active_settings_profile(name)
    except KeyError:
        raise typer.Exit(code=1)


@profiles_app.command("clear")
def profile_clear_active():
    """Clear the active profile."""

    set_active_settings_profile(None)


@profiles_app.command("delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile name"),
):
    """Delete a profile."""

    if not delete_settings_profile(name):
        raise typer.Exit(code=1)


@profiles_app.command("rename")
def profile_rename(
    old: str = typer.Argument(..., help="Old profile name"),
    new: str = typer.Argument(..., help="New profile name"),
):
    """Rename a profile."""

    if not rename_settings_profile(old, new):
        raise typer.Exit(code=1)


@profiles_app.command("export")
def profile_export(
    name: str = typer.Argument(..., help="Profile name"),
    output: Path = typer.Option(..., "--output", "-o", help="Output JSON file"),
):
    """Export a profile to a JSON file (portable)."""

    try:
        export_profile_to_path(name, output)
    except Exception:
        raise typer.Exit(code=1)


@profiles_app.command("import")
def profile_import(
    path: Path = typer.Argument(..., help="Path to exported profile JSON"),
    name: Optional[str] = typer.Option(None, "--name", help="Override name on import"),
):
    """Import a profile from a JSON file (portable)."""

    try:
        imported = import_profile_from_path(path, name_override=name)
    except Exception:
        raise typer.Exit(code=1)
    print(imported)


# --- EXPORT / IMPORT (Data) ---


@export_app.command("data")
def export_data(
    output: Path = typer.Argument(..., help="Output file path"),
    data_type: str = typer.Option(
        "both", "--type", help="Data to export: analytics, history, or both"
    ),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, csv, or yaml"),
    start_date: Optional[str] = typer.Option(
        None, "--start", help="Start date filter (ISO format)"
    ),
    end_date: Optional[str] = typer.Option(None, "--end", help="End date filter (ISO format)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Export analytics and/or history data

    Examples:
        promptc export data export.json
        promptc export data export.csv --type analytics --format csv
        promptc export data backup.yaml --format yaml --start 2025-01-01
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    try:
        manager = get_export_import_manager()
        result = manager.export_data(
            output_file=output,
            data_type=data_type,  # type: ignore
            format=format,  # type: ignore
            start_date=start_date,
            end_date=end_date,
        )

        if json_output:
            print(json.dumps(result, indent=2))
        else:
            info = f"""[bold green]✓ Export successful[/bold green]

File: {result["file"]}
Format: {result["format"]}
Type: {result["data_type"]}
Analytics: {result["analytics_count"]} records
History: {result["history_count"]} entries
Export Date: {result["export_date"]}"""

            if format == "csv" and data_type == "both":
                info += "\n\n[yellow]Note: CSV export created separate files for analytics and history[/yellow]"

            console.print(
                Panel(info, title="[bold cyan]Export Complete[/bold cyan]", border_style="cyan")
            )

    except Exception as e:
        console.print(f"[bold red]✗ Export failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@export_app.command("import")
def import_data(
    input_file: Path = typer.Argument(..., help="Input file path"),
    data_type: str = typer.Option(
        "both", "--type", help="Data to import: analytics, history, or both"
    ),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing data or replace"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Import analytics and/or history data

    Examples:
        promptc export import export.json
        promptc export import export.csv --type analytics --replace
        promptc export import backup.yaml --merge
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if not input_file.exists():
        console.print(f"[bold red]✗ File not found:[/bold red] {input_file}")
        raise typer.Exit(code=1)

    try:
        manager = get_export_import_manager()
        result = manager.import_data(
            input_file=input_file,
            data_type=data_type,  # type: ignore
            merge=merge,
        )

        if json_output:
            print(json.dumps(result, indent=2))
        else:
            mode = "Merged" if merge else "Replaced"
            info = f"""[bold green]✓ Import successful[/bold green]

File: {result["file"]}
Format: {result["format"]}
Mode: {mode}
Analytics: {result["analytics_imported"]} records imported
History: {result["history_imported"]} entries imported"""

            console.print(
                Panel(info, title="[bold cyan]Import Complete[/bold cyan]", border_style="cyan")
            )

    except Exception as e:
        console.print(f"[bold red]✗ Import failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@export_app.command("backup")
def backup_all(
    output_dir: Path = typer.Option(
        Path.home() / ".promptc" / "backups", "--dir", help="Backup directory"
    ),
    format: str = typer.Option("json", "--format", "-f", help="Backup format: json, csv, or yaml"),
):
    """
    Create a complete backup of all data

    Example:
        promptc export backup
        promptc export backup --dir ./my-backups --format yaml
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    # Create backup directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"promptc_backup_{timestamp}.{format}"
    output_file = output_dir / filename

    try:
        manager = get_export_import_manager()
        result = manager.export_data(
            output_file=output_file,
            data_type="both",
            format=format,  # type: ignore
        )

        info = f"""[bold green]✓ Backup created[/bold green]

Location: {result["file"]}
Format: {result["format"]}
Analytics: {result["analytics_count"]} records
History: {result["history_count"]} entries
Backup Date: {result["export_date"]}"""

        console.print(
            Panel(info, title="[bold cyan]Backup Complete[/bold cyan]", border_style="cyan")
        )

    except Exception as e:
        console.print(f"[bold red]✗ Backup failed:[/bold red] {e}")
        raise typer.Exit(code=1)
