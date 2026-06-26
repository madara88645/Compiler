"""Transform-family commands: `fix`, `compare`, and `pack`."""

from __future__ import annotations

import sys
import orjson
import typer
from typing import List, Optional
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from app.compiler import compile_text, compile_text_v2, optimize_ir
from app.emitters import (
    emit_expanded_prompt,
    emit_expanded_prompt_v2,
    emit_system_prompt,
    emit_system_prompt_v2,
    emit_user_prompt,
    emit_user_prompt_v2,
    emit_plan,
    emit_plan_v2,
)
from app.autofix import auto_fix_prompt, explain_fixes
from app.compare import compare_prompts
from app.utils import _render_prompt_pack_md, _render_prompt_pack_txt

from cli.commands._base import app, console
from cli.commands._helpers import _write_output

# Constants
HEURISTIC_VERSION = "1.0.0"
HEURISTIC2_VERSION = "2.0.0"


@app.command("fix")
def fix_prompt_command(
    text: List[str] = typer.Argument(None, help="Prompt text to fix"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read prompt from file"
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin"),
    apply: bool = typer.Option(
        False, "--apply", help="Apply fixes automatically (overwrite file if --from-file)"
    ),
    max_fixes: int = typer.Option(5, "--max-fixes", help="Maximum number of fixes to apply"),
    target_score: float = typer.Option(
        75.0, "--target-score", help="Stop when score reaches this threshold"
    ),
    show_diff: bool = typer.Option(True, "--diff/--no-diff", help="Show before/after diff"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write fixed prompt to file"),
):
    """Automatically fix prompt based on validation issues."""

    # Get prompt text
    if stdin:
        full_text = sys.stdin.read()
    elif from_file:
        if not from_file.exists():
            typer.echo(f"Error: File not found: {from_file}", err=True)
            raise typer.Exit(1)
        full_text = from_file.read_text(encoding="utf-8")
    elif text:
        full_text = " ".join(text)
    else:
        typer.echo("Error: Provide prompt text, --from-file, or --stdin", err=True)
        raise typer.Exit(1)

    if not full_text.strip():
        typer.echo("Error: Empty prompt", err=True)
        raise typer.Exit(1)

    # Run auto-fix
    result = auto_fix_prompt(full_text, max_fixes=max_fixes, min_score_target=target_score)

    # Prepare output
    if json_out:
        output_data = {
            "original_text": result.original_text,
            "fixed_text": result.fixed_text,
            "original_score": round(result.original_score, 1),
            "fixed_score": round(result.fixed_score, 1),
            "improvement": round(result.improvement, 1),
            "fixes_applied": [
                {
                    "type": fix.fix_type,
                    "description": fix.description,
                    "confidence": round(fix.confidence, 2),
                }
                for fix in result.fixes_applied
            ],
            "remaining_issues": result.remaining_issues,
        }
        # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
        output = orjson.dumps(output_data, option=orjson.OPT_INDENT_2).decode("utf-8")
        typer.echo(output)
    else:
        # Rich formatted output

        # Show report
        report = explain_fixes(result)
        console.print(
            Panel(report, title="[bold cyan]Auto-Fix Report[/bold cyan]", border_style="cyan")
        )

        # Show diff if requested
        if show_diff and result.fixes_applied:
            console.print("\n[bold]Changes:[/bold]")
            console.print("[dim]Original:[/dim]")
            console.print(Panel(result.original_text, border_style="red"))
            console.print("\n[dim]Fixed:[/dim]")
            console.print(Panel(result.fixed_text, border_style="green"))

        # Show what was fixed
        if result.fixes_applied:
            console.print("\n[bold]Applied Fixes:[/bold]")
            for i, fix in enumerate(result.fixes_applied, 1):
                color = "green" if fix.confidence > 0.7 else "yellow"
                console.print(f"  [{color}]{i}. {fix.description}[/{color}]")

    # Apply changes if requested
    if apply and from_file:
        from_file.write_text(result.fixed_text, encoding="utf-8")
        typer.echo(f"\n✓ Fixed prompt saved to {from_file}")

    # Save to output file
    if out:
        out.write_text(result.fixed_text, encoding="utf-8")
        typer.echo(f"✓ Fixed prompt saved to {out}")

    # Exit with success if improvement was made
    if result.improvement > 0:
        typer.echo(f"\n✓ Improvement: +{result.improvement:.1f} points")
    else:
        typer.echo("\n⚠ No improvements possible with current fix strategies")


@app.command("compare")
def compare_command(
    prompt_a: str = typer.Argument(..., help="First prompt (text or file path)"),
    prompt_b: str = typer.Argument(..., help="Second prompt (text or file path)"),
    label_a: str = typer.Option("Prompt A", "--label-a", "-la", help="Label for first prompt"),
    label_b: str = typer.Option("Prompt B", "--label-b", "-lb", help="Label for second prompt"),
    show_diff: bool = typer.Option(True, "--diff/--no-diff", help="Show IR diff"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Save comparison to file"),
):
    """Compare two prompts side by side."""

    # Load prompts (file or direct text)
    def load_prompt(text_or_file: str) -> str:
        p = Path(text_or_file)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")
        return text_or_file

    try:
        prompt_a_text = load_prompt(prompt_a)
        prompt_b_text = load_prompt(prompt_b)
    except Exception as e:
        typer.secho(f"Error loading prompts: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Compare
    with console.status(f"[bold blue]Comparing {label_a} vs {label_b}..."):
        result = compare_prompts(prompt_a_text, prompt_b_text, label_a, label_b)

    # JSON output
    if json_output:
        # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
        output = orjson.dumps(result.to_dict(), option=orjson.OPT_INDENT_2).decode("utf-8")
        if out:
            out.write_text(output, encoding="utf-8")
            typer.echo(f"✓ Comparison saved to {out}")
        else:
            typer.echo(output)
        return

    # Rich formatted output
    console.print(f"\n[bold cyan]Prompt Comparison: {label_a} vs {label_b}[/bold cyan]\n")

    # Score comparison table
    score_table = Table(title="📊 Validation Scores", show_header=True, header_style="bold magenta")
    score_table.add_column("Category", style="cyan", width=15)
    score_table.add_column(label_a, justify="center", style="blue", width=12)
    score_table.add_column(label_b, justify="center", style="blue", width=12)
    score_table.add_column("Difference", justify="center", style="yellow", width=12)
    score_table.add_column("Winner", justify="center", width=8)

    # Overall scores
    score_table.add_row(
        "Overall",
        f"{result.validation_a.score.total:.1f}",
        f"{result.validation_b.score.total:.1f}",
        f"{result.score_difference:+.1f}",
        "[green]●[/green]"
        if result.better_prompt == "B"
        else ("[red]●[/red]" if result.better_prompt == "A" else "[yellow]●[/yellow]"),
    )

    score_table.add_section()

    # Category scores
    for category, data in result.category_comparison.items():
        winner_symbol = ""
        if data["better"] == "A":
            winner_symbol = "[red]◄[/red]"
        elif data["better"] == "B":
            winner_symbol = "[green]►[/green]"
        else:
            winner_symbol = "[yellow]=[/yellow]"

        score_table.add_row(
            category.title(),
            f"{data['score_a']:.1f}",
            f"{data['score_b']:.1f}",
            f"{data['difference']:+.1f}",
            winner_symbol,
        )

    console.print(score_table)

    # Recommendation
    console.print("\n" + "=" * 80)
    console.print(
        Panel(
            Markdown(result.recommendation),
            title="[bold green]💡 Recommendation[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    # Save to file
    if out:
        output_data = result.to_dict()
        # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
        out.write_text(
            orjson.dumps(output_data, option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8"
        )
        typer.echo(f"\n✓ Comparison saved to {out}")


@app.command("pack")
def pack_command(
    text: List[str] = typer.Argument(
        None, help="Prompt text (wrap in quotes for multi-word)", show_default=False
    ),
    from_file: Path = typer.Option(
        None, "--from-file", help="Read prompt text from a file (UTF-8)"
    ),
    stdin: bool = typer.Option(
        False, "--stdin", help="Read prompt text from STDIN (overrides TEXT and --from-file)"
    ),
    fail_on_empty: bool = typer.Option(
        False,
        "--fail-on-empty",
        help="Exit with non-zero status if input is empty/whitespace",
    ),
    diagnostics: bool = typer.Option(
        False, "--diagnostics", help="Include diagnostics (risk & ambiguity) in expanded prompt"
    ),
    v1: bool = typer.Option(False, "--v1", help="Use legacy IR v1 and v1 prompt renderers"),
    format: str = typer.Option(
        "md",
        "--format",
        "-f",
        help="Output format: md|json|txt (default: md)",
    ),
    out: Path = typer.Option(None, "--out", help="Write output to a file (overwrites)"),
    out_dir: Path = typer.Option(
        None, "--out-dir", help="Write output to a directory (creates if missing)"
    ),
):
    """Export a single-file prompt pack (System/User/Plan/Expanded) for easy copy/paste."""

    if not text and not from_file and not stdin:
        raise typer.BadParameter("Provide TEXT, --from-file, or --stdin")

    if stdin:
        try:
            full_text = sys.stdin.read()
        except Exception as e:
            raise typer.BadParameter(f"Cannot read from STDIN: {e}")
    elif from_file is not None:
        try:
            full_text = from_file.read_text(encoding="utf-8")
        except Exception as e:
            raise typer.BadParameter(f"Cannot read file: {from_file} ({e})")
    else:
        full_text = " ".join(text)

    if fail_on_empty and not (full_text or "").strip():
        typer.secho("Input is empty", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if v1:
        ir = optimize_ir(compile_text(full_text))
        system_prompt = emit_system_prompt(ir)
        user_prompt = emit_user_prompt(ir)
        plan = emit_plan(ir)
        expanded = emit_expanded_prompt(ir, diagnostics=diagnostics)
        heur = HEURISTIC_VERSION
        ir_ver = "v1"
    else:
        ir2 = compile_text_v2(full_text)
        system_prompt = emit_system_prompt_v2(ir2)
        user_prompt = emit_user_prompt_v2(ir2)
        plan = emit_plan_v2(ir2)
        expanded = emit_expanded_prompt_v2(ir2, diagnostics=diagnostics)
        heur = HEURISTIC2_VERSION
        ir_ver = "v2"

    if v1:
        _domain = "—"
        _persona = getattr(ir, "persona", "—")
        _risk = "—"
    else:
        _ir2_json = ir2.model_dump()
        _domain = _ir2_json.get("domain") or "—"
        _persona = _ir2_json.get("persona") or "—"
        _risk = ((_ir2_json.get("metadata") or {}).get("policy_summary") or {}).get(
            "risk_level"
        ) or "—"
    pack_header = f"Domain: {_domain} | Persona: {_persona} | Risk: {_risk} | IR version: {ir_ver}"
    fmt_l = (format or "md").lower()
    if fmt_l in {"md", "markdown"}:
        payload = _render_prompt_pack_md(
            system_prompt, user_prompt, plan, expanded, header=pack_header
        )
        default_name = "prompt_pack.md"
    elif fmt_l == "txt":
        payload = _render_prompt_pack_txt(
            system_prompt, user_prompt, plan, expanded, header=pack_header
        )
        default_name = "prompt_pack.txt"
    elif fmt_l == "json":
        # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
        payload = orjson.dumps(
            {
                "ir_version": ir_ver,
                "heuristic_version": heur,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "plan": plan,
                "expanded_prompt": expanded,
            },
            option=orjson.OPT_INDENT_2,
        ).decode("utf-8")
        default_name = "prompt_pack.json"
    else:
        raise typer.BadParameter("Unknown --format. Use md|json|txt")

    if out or out_dir:
        _write_output(payload, out, out_dir, default_name=default_name)
        return

    typer.echo(payload)
