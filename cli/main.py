from __future__ import annotations
import json
from typing import List
import typer
from rich import print
from app.compiler import compile_text, optimize_ir
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt

app = typer.Typer(help="Prompt Compiler CLI")

@app.command()
def compile(text: List[str] = typer.Argument(..., help="Prompt metni: tırnak koymazsan kelimeler arası boşluklarla ayırabilirsin")):
    full_text = " ".join(text)
    ir = optimize_ir(compile_text(full_text))
    system_prompt = emit_system_prompt(ir)
    user_prompt = emit_user_prompt(ir)
    plan = emit_plan(ir)
    expanded = emit_expanded_prompt(ir)
    print(f"[bold white]Role:[/bold white] {ir.role}")
    print("\n[bold blue]IR JSON:[/bold blue]")
    print(json.dumps(ir.dict(), ensure_ascii=False, indent=2))
    print("\n[bold green]System Prompt:[/bold green]\n" + system_prompt)
    print("\n[bold magenta]User Prompt:[/bold magenta]\n" + user_prompt)
    print("\n[bold yellow]Plan:[/bold yellow]\n" + plan)
    print("\n[bold cyan]Expanded Prompt:[/bold cyan]\n" + expanded)

if __name__ == "__main__":  # pragma: no cover
    app()
