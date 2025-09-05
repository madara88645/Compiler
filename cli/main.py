from __future__ import annotations
import json
from typing import List
from pathlib import Path
import typer
from rich import print
from app.compiler import compile_text, compile_text_v2, optimize_ir, HEURISTIC_VERSION, HEURISTIC2_VERSION, generate_trace
from app.emitters import (
    emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt,
    emit_system_prompt_v2, emit_user_prompt_v2, emit_plan_v2, emit_expanded_prompt_v2,
)
from app import get_version

app = typer.Typer(help="Prompt Compiler CLI")

def _run_compile(
    full_text: str,
    diagnostics: bool,
    json_only: bool,
    quiet: bool,
    persona: str | None,
    trace: bool,
    v1: bool = False,
    render_v2: bool = False,
    out: Path | None = None,
    out_dir: Path | None = None,
    fmt: str | None = None,
):
    if v1:
        ir = optimize_ir(compile_text(full_text))
        ir2 = None
    else:
        ir2 = compile_text_v2(full_text)
        # For rendering, continue to use v1 emitters if needed; here we print IR JSON by default
        ir = None
    if persona and (ir is not None):
        ir.persona = persona.strip().lower()
    # Resolve quiet vs json_only
    if json_only and quiet:
        quiet = False
    system_prompt = emit_system_prompt(ir) if ir else (emit_system_prompt_v2(ir2) if (ir2 and render_v2) else "")
    if quiet:
        print(system_prompt)
        return
    user_prompt = emit_user_prompt(ir) if ir else (emit_user_prompt_v2(ir2) if (ir2 and render_v2) else "")
    plan = emit_plan(ir) if ir else (emit_plan_v2(ir2) if (ir2 and render_v2) else "")
    expanded = emit_expanded_prompt(ir, diagnostics=diagnostics) if ir else (emit_expanded_prompt_v2(ir2, diagnostics=diagnostics) if (ir2 and render_v2) else "")
    if json_only:
        data = ir.dict() if ir else ir2.dict()
        if trace:
            if ir:
                data['trace'] = generate_trace(ir)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        if out or out_dir:
            _write_output(payload, out, out_dir, default_name="ir.json")
            return
        print(payload)
        return
    if ir:
        print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
        print(f"[bold white]Role:[/bold white] {ir.role}")
    else:
        print(f"[bold white]IR v2[/bold white] (heuristics v{HEURISTIC2_VERSION})")
    print("\n[bold blue]IR JSON:[/bold blue]")
    ir_json = ir.dict() if ir else ir2.dict()
    if trace and ir:
        ir_json['trace'] = generate_trace(ir)
    rendered = json.dumps(ir_json, ensure_ascii=False, indent=2)
    if out or out_dir:
        # Support --format md to save prompts as Markdown
        if fmt and fmt.lower() == 'md' and ir:
            md_parts = [
                "# System Prompt\n\n" + system_prompt,
                "\n\n# User Prompt\n\n" + user_prompt,
                "\n\n# Plan\n\n" + plan,
                "\n\n# Expanded Prompt\n\n" + expanded,
                "\n\n# IR JSON\n\n```json\n" + rendered + "\n```",
            ]
            _write_output("\n".join(md_parts), out, out_dir, default_name="promptc.md")
            return
        _write_output(rendered, out, out_dir, default_name="ir.json")
        return
    print(rendered)
    if ir or (ir2 and render_v2):
        print("\n[bold green]System Prompt:[/bold green]\n" + system_prompt)
        print("\n[bold magenta]User Prompt:[/bold magenta]\n" + user_prompt)
        print("\n[bold yellow]Plan:[/bold yellow]\n" + plan)
        print("\n[bold cyan]Expanded Prompt:[/bold cyan]\n" + expanded)
def _write_output(content: str, out: Path | None, out_dir: Path | None, default_name: str = "output.txt"):
    target: Path
    if out:
        target = out
    else:
        directory = out_dir or Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / default_name
    target.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    print(f"[saved] {target}")

@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    text: List[str] = typer.Argument(None, help="Prompt text (omit to show help)", show_default=False),
    from_file: Path = typer.Option(None, "--from-file", help="Read prompt text from a file (UTF-8)"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"),
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON"),
    quiet: bool = typer.Option(False, "--quiet", help="Print only system prompt (overrides json-only)"),
    persona: str = typer.Option(None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"),
    trace: bool = typer.Option(False, "--trace", help="Print heuristic trace lines (stderr friendly)"),
    v1: bool = typer.Option(False, "--v1", help="Use legacy IR v1 output and render prompts"),
    render_v2: bool = typer.Option(False, "--render-v2", help="Render prompts using IR v2 emitters"),
    out: Path = typer.Option(None, "--out", help="Write output to a file (overwrites)"),
    out_dir: Path = typer.Option(None, "--out-dir", help="Write output to a directory (creates if missing)"),
    format: str = typer.Option(None, "--format", help="Output format when saving: md|json (default json)"),
):
    """If no subcommand is provided, behave like the compile command for convenience."""
    if ctx.invoked_subcommand is not None:
        return
    if not text and not from_file:
        # Show help if nothing supplied
        typer.echo(ctx.get_help())
        raise typer.Exit()
    if from_file is not None:
        try:
            full_text = from_file.read_text(encoding="utf-8")
        except Exception as e:
            raise typer.BadParameter(f"Cannot read file: {from_file} ({e})")
    else:
        full_text = " ".join(text)
    _run_compile(full_text, diagnostics, json_only, quiet, persona, trace, v1=v1, render_v2=render_v2, out=out, out_dir=out_dir, fmt=format)

@app.command()
def compile(
    text: List[str] = typer.Argument(None, help="Prompt text (wrap in quotes for multi-word)", show_default=False),
    from_file: Path = typer.Option(None, "--from-file", help="Read prompt text from a file (UTF-8)"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"),
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON"),
    quiet: bool = typer.Option(False, "--quiet", help="Print only system prompt (overrides json-only)"),
    persona: str = typer.Option(None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"),
    trace: bool = typer.Option(False, "--trace", help="Print heuristic trace lines (stderr friendly)"),
    v1: bool = typer.Option(False, "--v1", help="Use legacy IR v1 output and render prompts"),
    render_v2: bool = typer.Option(False, "--render-v2", help="Render prompts using IR v2 emitters"),
    out: Path = typer.Option(None, "--out", help="Write output to a file (overwrites)"),
    out_dir: Path = typer.Option(None, "--out-dir", help="Write output to a directory (creates if missing)"),
    format: str = typer.Option(None, "--format", help="Output format when saving: md|json (default json)"),
):
    if not text and not from_file:
        raise typer.BadParameter("Provide TEXT or --from-file")
    if from_file is not None:
        try:
            full_text = from_file.read_text(encoding="utf-8")
        except Exception as e:
            raise typer.BadParameter(f"Cannot read file: {from_file} ({e})")
    else:
        full_text = " ".join(text)
    _run_compile(full_text, diagnostics, json_only, quiet, persona, trace, v1=v1, render_v2=render_v2, out=out, out_dir=out_dir, fmt=format)

if __name__ == "__main__":  # pragma: no cover
    app()

@app.command()
def version():
    """Print package version."""
    print(get_version())
