"""Validation command: `validate`."""

from __future__ import annotations

import json
import typer
from typing import List
from pathlib import Path

from app.resources import get_ir_schema_json

from cli.commands._base import app


@app.command("validate")
def validate(
    files: List[Path] = typer.Argument(..., help="JSON files to validate (v1 or v2)"),
):
    """Validate IR JSON against schema."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        typer.secho(
            "jsonschema not installed. Install with 'pip install jsonschema'", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    ok = 0
    fail = 0
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            fail += 1
            typer.secho(f"[fail] {p}: {e}", fg=typer.colors.RED)
            continue
        # Choose schema by version
        v2 = isinstance(data, dict) and data.get("version") == "2.0"
        try:
            schema = get_ir_schema_json(v2=v2)
            Draft202012Validator(schema).validate(data)
            ok += 1
            typer.secho(f"[ok] {p}", fg=typer.colors.GREEN)
        except Exception as e:
            fail += 1
            typer.secho(f"[fail] {p}: {e}", fg=typer.colors.RED)

    total = ok + fail
    summary = f"Summary: OK={ok} Failed={fail} Total={total}"
    typer.echo(summary)
    if fail:
        raise typer.Exit(code=1)
