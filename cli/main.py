from __future__ import annotations
import json
from typing import List
import typer
from rich import print
from app.compiler import compile_text, optimize_ir, HEURISTIC_VERSION, generate_trace
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt
from app import get_version

app = typer.Typer(help="Prompt Compiler CLI")

def _run_compile(full_text: str, diagnostics: bool, json_only: bool, quiet: bool, persona: str | None, trace: bool):
    ir = optimize_ir(compile_text(full_text))
    if persona:
        ir.persona = persona.strip().lower()
    # Resolve quiet vs json_only
    if json_only and quiet:
        quiet = False
    system_prompt = emit_system_prompt(ir)
    if quiet:
        print(system_prompt)
        return
    user_prompt = emit_user_prompt(ir)
    plan = emit_plan(ir)
    expanded = emit_expanded_prompt(ir, diagnostics=diagnostics)
    if json_only:
        data = ir.dict()
        if trace:
            data['trace'] = generate_trace(ir)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
    print(f"[bold white]Role:[/bold white] {ir.role}")
    print("\n[bold blue]IR JSON:[/bold blue]")
    ir_json = ir.dict()
    if trace:
        ir_json['trace'] = generate_trace(ir)
    print(json.dumps(ir_json, ensure_ascii=False, indent=2))
    print("\n[bold green]System Prompt:[/bold green]\n" + system_prompt)
    print("\n[bold magenta]User Prompt:[/bold magenta]\n" + user_prompt)
    print("\n[bold yellow]Plan:[/bold yellow]\n" + plan)
    print("\n[bold cyan]Expanded Prompt:[/bold cyan]\n" + expanded)

@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    text: List[str] = typer.Argument(None, help="Prompt text (omit to show help)", show_default=False),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"),
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON"),
    quiet: bool = typer.Option(False, "--quiet", help="Print only system prompt (overrides json-only)"),
    persona: str = typer.Option(None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"),
    trace: bool = typer.Option(False, "--trace", help="Print heuristic trace lines (stderr friendly)"),
):
    """If no subcommand is provided, behave like the compile command for convenience."""
    if ctx.invoked_subcommand is not None:
        return
    if not text:
        # Show help if nothing supplied
        typer.echo(ctx.get_help())
        raise typer.Exit()
    full_text = " ".join(text)
    _run_compile(full_text, diagnostics, json_only, quiet, persona, trace)

@app.command()
def compile(
    text: List[str] = typer.Argument(..., help="Prompt text (wrap in quotes for multi-word)"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"),
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON"),
    quiet: bool = typer.Option(False, "--quiet", help="Print only system prompt (overrides json-only)"),
    persona: str = typer.Option(None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"),
    trace: bool = typer.Option(False, "--trace", help="Print heuristic trace lines (stderr friendly)"),
):
    full_text = " ".join(text)
    _run_compile(full_text, diagnostics, json_only, quiet, persona, trace)

if __name__ == "__main__":  # pragma: no cover
    app()

@app.command()
def version():
    """Print package version."""
    print(get_version())
