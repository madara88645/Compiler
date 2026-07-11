"""JSON utility commands: `json-path` and `diff`.

Named `json_tools` (not `json`) to avoid shadowing the stdlib `json` module.
"""

from __future__ import annotations

import json
import orjson
import difflib
import re
import typer
from typing import Any, List, Optional
from pathlib import Path
from rich import print

from cli.commands._base import app


@app.command("json-path")
def json_path(
    file: Path = typer.Argument(..., help="JSON file path"),
    path: str = typer.Argument(..., help="Dot path into JSON, e.g. metadata.ir_signature"),
    raw: bool = typer.Option(False, "--raw", help="Print raw value without quotes when scalar"),
    default: Optional[str] = typer.Option(
        None,
        "--default",
        help="Fallback value to print when path is not found (exits 0 instead of 1)",
    ),
    show_type: bool = typer.Option(
        False,
        "--type",
        help="Print JSON type of the value (object|array|string|number|bool|null)",
    ),
):
    """Navigate JSON with simple path syntax including list indexes."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    token_re = re.compile(r"([A-Za-z0-9_\-]+)|\[(\d+)\]")
    segments: list[str | int] = []
    for dot_part in [p for p in path.split(".") if p]:
        idx = 0
        while idx < len(dot_part):
            m = token_re.match(dot_part, idx)
            if not m:
                if default is not None:
                    typer.echo(default)
                    raise typer.Exit(code=0)
                typer.secho("<not-found>", fg=typer.colors.YELLOW)
                raise typer.Exit(code=1)
            if m.group(1):
                segments.append(m.group(1))
            else:
                segments.append(int(m.group(2)))
            idx = m.end()

    cur: Any = data
    for seg in segments:
        if isinstance(seg, str):
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                if default is not None:
                    typer.echo(default)
                    raise typer.Exit(code=0)
                typer.secho("<not-found>", fg=typer.colors.YELLOW)
                raise typer.Exit(code=1)
        else:  # list index
            if isinstance(cur, list) and 0 <= seg < len(cur):
                cur = cur[seg]
            else:
                if default is not None:
                    typer.echo(default)
                    raise typer.Exit(code=0)
                typer.secho("<not-found>", fg=typer.colors.YELLOW)
                raise typer.Exit(code=1)

    if show_type:

        def _jtype(v: Any) -> str:
            if v is None:
                return "null"
            if isinstance(v, bool):
                return "bool"
            if isinstance(v, (int, float)):
                return "number"
            if isinstance(v, str):
                return "string"
            if isinstance(v, list):
                return "array"
            if isinstance(v, dict):
                return "object"
            return type(v).__name__

        typer.echo(_jtype(cur))
        return

    if raw and isinstance(cur, (int, float)):
        typer.echo(str(cur))
    elif raw and isinstance(cur, str):
        typer.echo(cur)
    else:
        typer.echo(json.dumps(cur, ensure_ascii=False))


def _parse_path_segments(path: str) -> list[str | int]:
    """Parse a dot-separated path with optional [N] bracket indexes into segments."""
    token_re = re.compile(r"([A-Za-z0-9_\-]+)|\[(\d+)\]")
    segments: list[str | int] = []
    for dot_part in [p for p in path.split(".") if p]:
        idx = 0
        while idx < len(dot_part):
            m = token_re.match(dot_part, idx)
            if not m:
                break
            if m.group(1):
                segments.append(m.group(1))
            else:
                segments.append(int(m.group(2)))
            idx = m.end()
    return segments


def _delete_paths(obj: Any, paths: list[str]) -> None:
    """Delete each path from *obj* in-place, silently skipping missing paths."""
    for path in paths:
        segments = _parse_path_segments(path)
        if not segments:
            continue
        cur = obj
        for seg in segments[:-1]:
            if isinstance(seg, str) and isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            elif isinstance(seg, int) and isinstance(cur, list) and 0 <= seg < len(cur):
                cur = cur[seg]
            else:
                cur = None
                break
        if cur is None:
            continue
        last = segments[-1]
        if isinstance(last, str) and isinstance(cur, dict):
            cur.pop(last, None)
        elif isinstance(last, int) and isinstance(cur, list) and 0 <= last < len(cur):
            del cur[last]


@app.command("diff")
def json_diff(
    a: Path = typer.Argument(..., help="First JSON file"),
    b: Path = typer.Argument(..., help="Second JSON file"),
    context: int = typer.Option(3, "--context", help="Number of context lines for unified diff"),
    color: bool = typer.Option(False, "--color", help="Colorize diff output"),
    sort_keys: bool = typer.Option(
        False, "--sort-keys", help="Sort JSON object keys before diff (reduces noise)"
    ),
    brief: bool = typer.Option(
        False,
        "--brief",
        help="Exit with status 1 if files differ, print nothing (good for CI)",
    ),
    ignore_path: List[str] = typer.Option(
        None,
        "--ignore-path",
        help="Dot/list paths to ignore (repeatable), e.g. metadata.ir_signature or steps[0]",
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write diff to a file"),
):
    """Compare two JSON files."""
    try:
        ja = json.loads(a.read_text(encoding="utf-8"))
        jb = json.loads(b.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    # Optionally delete ignored paths
    if ignore_path:
        _delete_paths(ja, ignore_path)
        _delete_paths(jb, ignore_path)

    if brief:
        if ja == jb:
            return
        raise typer.Exit(code=1)

    # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
    opt = orjson.OPT_INDENT_2
    if sort_keys:
        opt |= orjson.OPT_SORT_KEYS

    sa = orjson.dumps(ja, option=opt).decode("utf-8").splitlines(keepends=False)
    sb = orjson.dumps(jb, option=opt).decode("utf-8").splitlines(keepends=False)

    diff = difflib.unified_diff(sa, sb, fromfile=str(a), tofile=str(b), n=context)

    if not color:
        txt = "".join(line + "\n" if not line.endswith("\n") else line for line in diff)
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(txt, encoding="utf-8")
        else:
            typer.echo(txt)
    else:
        colored_lines: list[str] = []
        for line in diff:
            ln = line if line.endswith("\n") else line + "\n"
            if line.startswith("+++") or line.startswith("---"):
                colored_lines.append(f"[bold]{ln.rstrip()}[/bold]")
            elif line.startswith("@@"):
                colored_lines.append(f"[cyan]{ln.rstrip()}[/cyan]")
            elif line.startswith("+") and not line.startswith("+++"):
                colored_lines.append(f"[green]{ln.rstrip()}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                colored_lines.append(f"[red]{ln.rstrip()}[/red]")
            else:
                colored_lines.append(ln.rstrip())

        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(colored_lines) + "\n", encoding="utf-8")
        else:
            for cl in colored_lines:
                print(cl)
