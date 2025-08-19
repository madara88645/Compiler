from __future__ import annotations
import json
from typing import List
import typer
from rich import print
from app.compiler import compile_text, optimize_ir, HEURISTIC_VERSION
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt
from app import get_version

app = typer.Typer(help="Prompt Compiler CLI")

@app.command()
def compile(
    text: List[str] = typer.Argument(..., help="Prompt text (wrap in quotes for multi-word)"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"),
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON"),
    quiet: bool = typer.Option(False, "--quiet", help="Print only system prompt (overrides json-only)"),
    persona: str = typer.Option(None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"),
):
    full_text = " ".join(text)
    ir = optimize_ir(compile_text(full_text))
    if persona:
        ir.persona = persona.strip().lower()
    if json_only and quiet:
        quiet = False  # prioritize quiet? Choose system prompt only; resolve by disabling json_only
    system_prompt = emit_system_prompt(ir)
    if quiet:
        print(system_prompt)
        return
    system_prompt = emit_system_prompt(ir)
    user_prompt = emit_user_prompt(ir)
    plan = emit_plan(ir)
    expanded = emit_expanded_prompt(ir, diagnostics=diagnostics)
    if json_only:
        print(json.dumps(ir.dict(), ensure_ascii=False, indent=2))
        return
    print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
    print(f"[bold white]Role:[/bold white] {ir.role}")
    print("\n[bold blue]IR JSON:[/bold blue]")
    print(json.dumps(ir.dict(), ensure_ascii=False, indent=2))
    print("\n[bold green]System Prompt:[/bold green]\n" + system_prompt)
    print("\n[bold magenta]User Prompt:[/bold magenta]\n" + user_prompt)
    print("\n[bold yellow]Plan:[/bold yellow]\n" + plan)
    print("\n[bold cyan]Expanded Prompt:[/bold cyan]\n" + expanded)

if __name__ == "__main__":  # pragma: no cover
    app()

@app.command()
def version():
    """Print package version."""
    print(get_version())
