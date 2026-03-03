from __future__ import annotations
import json
import typer
from rich import print
from typing import Optional
from pathlib import Path

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

plugins_app = typer.Typer(help="Plugin utilities")
profiles_app = typer.Typer(help="Settings profiles shared with the desktop UI")

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
