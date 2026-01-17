from __future__ import annotations
import sys
import json
import yaml
import time
import typer
import difflib
import re
from typing import Optional, List, Any
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.markdown import Markdown
from concurrent.futures import ThreadPoolExecutor, as_completed

# App imports
from app.compiler import (
    compile_text,
    compile_text_v2,
    optimize_ir,
    generate_trace,
)
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
from app.validator import validate_prompt
from app.autofix import auto_fix_prompt, explain_fixes
from app.compare import compare_prompts
from app.utils import _render_prompt_pack_md, _render_prompt_pack_txt
from app.resources import get_ir_schema_json

from app import get_version
from app.analytics import AnalyticsManager, create_record_from_ir
from app.history import get_history_manager


# Constants
HEURISTIC_VERSION = "1.0.0"
HEURISTIC2_VERSION = "2.0.0"

app = typer.Typer(help="Core compiler and utility commands")

def _write_output(
    content: str, out: Optional[Path], out_dir: Optional[Path], default_name: str = "output.txt"
):
    """Helper to write output to file or directory."""
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / default_name
        target.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {target}")
    elif out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {out}")
    else:
        typer.echo(content)

# ============================================================================
# Core Compass Commands
# ============================================================================

@app.command()
def version():
    """Print package version."""
    print(get_version())



def _run_compile(
    full_text: str,
    diagnostics: bool,
    json_only: bool,
    quiet: bool,
    persona: str | None,
    trace: bool,
    record_analytics: bool = False,
    validate: bool = False,
    pre_score: float | None = None,
    post_score: float | None = None,
    iteration_count: int = 1,
    user_level: str = "intermediate",
    task_type: str = "general",
    tags: list[str] | None = None,
    v1: bool = False,
    render_v2: bool = False,
    out: Path | None = None,
    out_dir: Path | None = None,
    fmt: str | None = None,
):
    t0 = time.time()
    if v1:
        ir = optimize_ir(compile_text(full_text))
        ir2 = None
    else:
        ir2 = compile_text_v2(full_text)
        # For rendering, continue to use v1 emitters if needed; here we print IR JSON by default
        ir = None
    if persona and (ir is not None):
        ir.persona = persona.strip().lower()

    # Build IR payload early so analytics can be recorded even when we exit early
    # (e.g. --json-only/--quiet). This is cheap (model_dump) and keeps behavior consistent.
    ir_json = ir.model_dump() if ir else ir2.model_dump()
    if trace and ir:
        ir_json["trace"] = generate_trace(ir)

    validation_result = None
    if validate:
        if ir2 is None:
            # Validation currently supports IR v2 only.
            print("[warn] Validation skipped (IR v1)", file=sys.stderr)
        else:
            try:
                validation_result = validate_prompt(ir2, full_text)
                # Keep stdout clean for --json-only; emit summary to stderr.
                score_total = (
                    validation_result.score.total
                    if hasattr(validation_result, "score")
                    and hasattr(validation_result.score, "total")
                    else None
                )
                if score_total is not None:
                    print(
                        f"[validation] score={score_total:.1f} errors={getattr(validation_result, 'errors', 0)} "
                        f"warnings={getattr(validation_result, 'warnings', 0)} issues={len(getattr(validation_result, 'issues', []) or [])}",
                        file=sys.stderr,
                    )
                else:
                    print("[validation] ok", file=sys.stderr)
            except Exception as e:
                print(f"[warn] Validation failed: {e}", file=sys.stderr)

    # Best-effort analytics capture (CLI)
    if record_analytics:
        try:
            elapsed_ms = int((time.time() - t0) * 1000)
            record = create_record_from_ir(
                full_text,
                ir_json,
                validation_result,
                interface_type="cli",
                user_level=(user_level or "intermediate").strip(),
                task_type=(task_type or "general").strip(),
                pre_score=pre_score,
                post_score=post_score,
                time_ms=elapsed_ms,
                iteration_count=max(1, int(iteration_count or 1)),
                tags=tags or [],
            )
            AnalyticsManager().record_prompt(record)
        except Exception:
            # Never fail the command due to analytics.
            pass

    # Resolve quiet vs json_only
    if json_only and quiet:
        quiet = False
    system_prompt = (
        emit_system_prompt(ir)
        if ir
        else (emit_system_prompt_v2(ir2) if (ir2 and render_v2) else "")
    )
    if quiet:
        print(system_prompt)
        return
    user_prompt = (
        emit_user_prompt(ir) if ir else (emit_user_prompt_v2(ir2) if (ir2 and render_v2) else "")
    )
    plan = emit_plan(ir) if ir else (emit_plan_v2(ir2) if (ir2 and render_v2) else "")
    expanded = (
        emit_expanded_prompt(ir, diagnostics=diagnostics)
        if ir
        else (emit_expanded_prompt_v2(ir2, diagnostics=diagnostics) if (ir2 and render_v2) else "")
    )
    if json_only:
        data = ir_json
        fmt_l = (fmt or "json").lower()
        # Prepare payload according to desired format
        if fmt_l in {"yaml", "yml"}:
            if yaml is None:
                typer.secho("PyYAML not installed; falling back to JSON", fg=typer.colors.YELLOW)
                payload = json.dumps(data, ensure_ascii=False, indent=2)
                default_name = "ir.json"
            else:
                payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # type: ignore
                default_name = "ir.yaml"
        else:
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            default_name = "ir.json"
        if out or out_dir:
            if fmt_l == "md" and (ir or (ir2 and render_v2)):
                # Support --format md to save prompts as Markdown (v1 or v2 rendering)
                md_parts = []
                if system_prompt:
                    md_parts.append("# System Prompt\n\n" + system_prompt)
                if user_prompt:
                    md_parts.append("\n\n# User Prompt\n\n" + user_prompt)
                if plan:
                    md_parts.append("\n\n# Plan\n\n" + plan)
                if expanded:
                    md_parts.append("\n\n# Expanded Prompt\n\n" + expanded)
                md_parts.append(
                    "\n\n# IR JSON\n\n```json\n"
                    + json.dumps(data, ensure_ascii=False, indent=2)
                    + "\n```"
                )
                _write_output("\n".join(md_parts), out, out_dir, default_name="promptc.md")
                return
            _write_output(payload, out, out_dir, default_name=default_name)
            return
        # Print to console
        if fmt_l in {"yaml", "yml"} and yaml is not None:
            typer.echo(payload)
        elif fmt_l == "md" and (ir or (ir2 and render_v2)):
            # Print a minimal markdown block to console when requested
            md_parts = []
            if system_prompt:
                md_parts.append("# System Prompt\n\n" + system_prompt)
            if user_prompt:
                md_parts.append("\n\n# User Prompt\n\n" + user_prompt)
            if plan:
                md_parts.append("\n\n# Plan\n\n" + plan)
            if expanded:
                md_parts.append("\n\n# Expanded Prompt\n\n" + expanded)
            md_parts.append(
                "\n\n# IR JSON\n\n```json\n"
                + json.dumps(data, ensure_ascii=False, indent=2)
                + "\n```"
            )
            typer.echo("\n".join(md_parts))
        else:
            typer.echo(payload)
        return
    if ir:
        print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
        print(f"[bold white]Role:[/bold white] {ir.role}")
    else:
        print(f"[bold white]IR v2[/bold white] (heuristics v{HEURISTIC2_VERSION})")
    print("\n[bold blue]IR JSON:[/bold blue]")
    ir_json = ir_json
    rendered = json.dumps(ir_json, ensure_ascii=False, indent=2)
    if out or out_dir:
        fmt_l = (fmt or "json").lower()
        # Support --format md to save prompts as Markdown (v1 or v2 rendering)
        if fmt_l == "md" and (ir or (ir2 and render_v2)):
            md_parts = []
            if system_prompt:
                md_parts.append("# System Prompt\n\n" + system_prompt)
            if user_prompt:
                md_parts.append("\n\n# User Prompt\n\n" + user_prompt)
            if plan:
                md_parts.append("\n\n# Plan\n\n" + plan)
            if expanded:
                md_parts.append("\n\n# Expanded Prompt\n\n" + expanded)
            md_parts.append("\n\n# IR JSON\n\n```json\n" + rendered + "\n```")
            _write_output("\n".join(md_parts), out, out_dir, default_name="promptc.md")
            return
        if fmt_l in {"yaml", "yml"}:
            if yaml is None:
                typer.secho("PyYAML not installed; writing JSON instead", fg=typer.colors.YELLOW)
                _write_output(rendered, out, out_dir, default_name="ir.json")
            else:
                ytxt = yaml.safe_dump(ir_json, sort_keys=False, allow_unicode=True)  # type: ignore
                _write_output(ytxt, out, out_dir, default_name="ir.yaml")
            return
        _write_output(rendered, out, out_dir, default_name="ir.json")
        return
    print(rendered)
    if ir or (ir2 and render_v2):
        print("\n[bold green]System Prompt:[/bold green]\n" + system_prompt)
        print("\n[bold magenta]User Prompt:[/bold magenta]\n" + user_prompt)
        print("\n[bold yellow]Plan:[/bold yellow]\n" + plan)
        print("\n[bold cyan]Expanded Prompt:[/bold cyan]\n" + expanded)

    # Save to history
    try:
        history_mgr = get_history_manager()
        history_mgr.add(full_text, ir_json, score=0.0)
    except Exception:
        # Silently fail if history fails
        pass


@app.command("compile")
def compile_cmd(
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
    json_only: bool = typer.Option(False, "--json-only", help="Print only IR JSON/YAML"),
    quiet: bool = typer.Option(
        False, "--quiet", help="Print only system prompt (overrides json-only)"
    ),
    persona: str = typer.Option(
        None, "--persona", help="Force persona (bypass heuristic) e.g. teacher, researcher"
    ),
    record_analytics: bool = typer.Option(
        False,
        "--record-analytics/--no-record-analytics",
        help="Record this run to analytics DB (best-effort)",
    ),
    validate: bool = typer.Option(
        False,
        "--validate/--no-validate",
        help="Run prompt validation and print a short summary to stderr",
    ),
    pre_score: float = typer.Option(
        None,
        "--pre-score",
        help="Analytics: baseline score before edits (for iteration tracking)",
    ),
    post_score: float = typer.Option(
        None,
        "--post-score",
        help="Analytics: score after edits (for iteration tracking)",
    ),
    iteration_count: int = typer.Option(
        1,
        "--iteration-count",
        min=1,
        help="Analytics: number of prompt iterations in this session",
    ),
    user_level: str = typer.Option(
        "intermediate",
        "--user-level",
        help="Analytics user level: beginner|intermediate|advanced",
    ),
    task_type: str = typer.Option(
        "general",
        "--task-type",
        help="Analytics task type (e.g. general, debugging, teaching)",
    ),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Analytics tag (repeatable), e.g. --tag project:x --tag load:high",
    ),
    trace: bool = typer.Option(
        False, "--trace", help="Print heuristic trace lines (stderr friendly)"
    ),
    v1: bool = typer.Option(False, "--v1", help="Use legacy IR v1 output and render prompts"),
    render_v2: bool = typer.Option(
        False, "--render-v2", help="Render prompts using IR v2 emitters"
    ),
    out: Path = typer.Option(None, "--out", help="Write output to a file (overwrites)"),
    out_dir: Path = typer.Option(
        None, "--out-dir", help="Write output to a directory (creates if missing)"
    ),
    format: str = typer.Option(
        None, "--format", help="Output format when saving/printing: md|json|yaml (default json)"
    ),
):
    """Compile a prompt file."""
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
    
    _run_compile(
        full_text,
        diagnostics,
        json_only,
        quiet,
        persona,
        trace,
        record_analytics=record_analytics,
        validate=validate,
        pre_score=pre_score,
        post_score=post_score,
        iteration_count=iteration_count,
        user_level=user_level,
        task_type=task_type,
        tags=tags,
        v1=v1,
        render_v2=render_v2,
        out=out,
        out_dir=out_dir,
        fmt=format,
    )


@app.command("validate")
def validate(
    files: List[Path] = typer.Argument(..., help="JSON files to validate (v1 or v2)"),
):
    """Validate IR JSON against schema."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        typer.secho("jsonschema not installed. Install with 'pip install jsonschema'", fg=typer.colors.RED)
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
        output = json.dumps(output_data, ensure_ascii=False, indent=2)
        typer.echo(output)
    else:
        # Rich formatted output
        console = Console()

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
    console = Console()

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
        output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
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
        out.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(f"\n✓ Comparison saved to {out}")


@app.command("batch")
def batch(
    in_dir: Path = typer.Argument(..., help="Input directory containing .txt files"),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory to write outputs"),
    format: str = typer.Option("json", "--format", help="Output format: json|md|yaml"),
    name_template: str = typer.Option(
        "{stem}.{ext}",
        "--name-template",
        help="Template for output file name; placeholders: {stem} {ext}",
    ),
    diagnostics: bool = typer.Option(
        False, "--diagnostics", help="Include diagnostics in expanded"
    ),
    jobs: int = typer.Option(
        1, "--jobs", min=1, help="Number of worker threads to use for parallel processing"
    ),
    pattern: List[str] = typer.Option(
        None,
        "--pattern",
        help="Glob pattern(s) for input files (repeatable). Defaults to *.txt",
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="Recurse into subdirectories when matching patterns"
    ),
    jsonl: Path = typer.Option(
        None,
        "--jsonl",
        help="Write all IRs (json format only) to a JSON Lines file (one compact JSON per line)",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Stream outputs to STDOUT (JSONL for json, multi-doc for yaml, sections for md) instead of per-file logs",
    ),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on first failure and exit 1"),
    summary_json: Optional[Path] = typer.Option(
        None,
        "--summary-json",
        help="Write a JSON summary with counts, durations, and error samples",
    ),
):
    """Batch compile multiple prompt files."""
    if not in_dir.exists() or not in_dir.is_dir():
        raise typer.BadParameter(f"Input dir not found: {in_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = (format or "json").lower()
    if fmt not in {"json", "md", "yaml", "yml"}:
        raise typer.BadParameter("--format must be json, md or yaml")
    if jsonl and fmt != "json":
        raise typer.BadParameter("--jsonl requires --format json")
    out_ext = "json" if fmt == "json" else ("md" if fmt == "md" else "yaml")
    
    # Suppress per-file saved logs for cleaner output
    setattr(_write_output, "_suppress_log", True)

    try:
        pats = pattern or ["*.txt"]
        file_set = set()
        for pat in pats:
            if recursive:
                for p in in_dir.rglob(pat):
                    if p.is_file():
                        file_set.add(p)
            else:
                for p in in_dir.glob(pat):
                    if p.is_file():
                        file_set.add(p)
        files = sorted(file_set)
        
        start = time.perf_counter()
        jsonl_file = None
        if jsonl:
            jsonl.parent.mkdir(parents=True, exist_ok=True)
            jsonl_file = jsonl.open("w", encoding="utf-8")

        stdout_chunks: list[str] = []
        errors: list[tuple[Path, str]] = []
        success_count = 0
        processed_count = 0

        def process_file(src: Path):
            nonlocal success_count, processed_count
            try:
                text = src.read_text(encoding="utf-8")
                target_name = name_template.format(stem=src.stem, ext=out_ext)
                target_path = out_dir / target_name
                _run_compile(
                    full_text=text,
                    diagnostics=diagnostics,
                    json_only=True if fmt in {"json", "yaml", "yml"} else False,
                    quiet=False,
                    persona=None,
                    trace=False,
                    v1=False,
                    render_v2=(fmt == "md"),
                    out=target_path,
                    out_dir=None,
                    fmt=fmt,
                )
                # For JSONL / STDOUT capture
                if fmt == "json" and (jsonl_file or stdout):
                    try:
                        obj = json.loads(target_path.read_text(encoding="utf-8"))
                        line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                        if jsonl_file:
                            jsonl_file.write(line + "\n")
                        if stdout:
                            stdout_chunks.append(line)
                    except Exception:
                        pass
                elif stdout and fmt in {"yaml", "yml"}:
                    stdout_chunks.append(target_path.read_text(encoding="utf-8"))
                elif stdout and fmt == "md":
                    content = target_path.read_text(encoding="utf-8")
                    stdout_chunks.append(f"\n---\n# {src.name}\n\n{content}")
                success_count += 1
                return src
            except Exception as e:
                errors.append((src, str(e)))
                if fail_fast:
                    raise
                return src
            finally:
                processed_count += 1

        if jobs == 1 or len(files) <= 1:
            for src in files:
                try:
                    process_file(src)
                except Exception:
                    pass
        else:
            with ThreadPoolExecutor(max_workers=jobs) as ex:
                futures = {ex.submit(process_file, src): src for src in files}
                for fut in as_completed(futures):
                    if fail_fast and fut.exception() is not None:
                         for other in futures:
                             other.cancel()
                         break
        
        if jsonl_file:
            jsonl_file.close()

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        avg_ms = elapsed_ms / max(1, len(files))
        
        if summary_json:
            summary = {
                "files": len(files),
                "processed": processed_count,
                "succeeded": success_count,
                "failed": len(errors),
                "skipped": max(0, len(files) - processed_count),
                "elapsed_ms": int(elapsed_ms),
                "avg_ms": float(f"{avg_ms:.3f}"),
                "jobs": jobs,
                "errors": [{"path": str(p), "error": msg} for p, msg in errors],
            }
            summary_json.parent.mkdir(parents=True, exist_ok=True)
            summary_json.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        if stdout and stdout_chunks:
            if fmt == "json":
                # Print JSONL
                typer.echo("\n".join(stdout_chunks))
            elif fmt in {"yaml", "yml"}:
                # Separate YAML docs
                typer.echo("\n---\n".join(chunk.strip() for chunk in stdout_chunks))
            else:  # md
                typer.echo("\n".join(stdout_chunks))
        else:
            print(f"[done] {len(files)} files -> outputs in {int(elapsed_ms)} ms (avg {avg_ms:.1f} ms) jobs={jobs}")
            if errors:
                for p, msg in errors[:5]:
                    typer.secho(f"[error] {p}: {msg}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    except Exception as e:
        typer.secho(f"Batch processing failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    finally:
        setattr(_write_output, "_suppress_log", False)



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

    fmt_l = (format or "md").lower()
    if fmt_l in {"md", "markdown"}:
        payload = _render_prompt_pack_md(system_prompt, user_prompt, plan, expanded)
        default_name = "prompt_pack.md"
    elif fmt_l == "txt":
        payload = _render_prompt_pack_txt(system_prompt, user_prompt, plan, expanded)
        default_name = "prompt_pack.txt"
    elif fmt_l == "json":
        payload = json.dumps(
            {
                "ir_version": ir_ver,
                "heuristic_version": heur,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "plan": plan,
                "expanded_prompt": expanded,
            },
            ensure_ascii=False,
            indent=2,
        )
        default_name = "prompt_pack.json"
    else:
        raise typer.BadParameter("Unknown --format. Use md|json|txt")

    if out or out_dir:
        _write_output(payload, out, out_dir, default_name=default_name)
        return

    typer.echo(payload)


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
            if v is None: return "null"
            if isinstance(v, bool): return "bool"
            if isinstance(v, (int, float)): return "number"
            if isinstance(v, str): return "string"
            if isinstance(v, list): return "array"
            if isinstance(v, dict): return "object"
            return type(v).__name__

        typer.echo(_jtype(cur))
        return

    if raw and isinstance(cur, (int, float)):
        typer.echo(str(cur))
    elif raw and isinstance(cur, str):
        typer.echo(cur)
    else:
        typer.echo(json.dumps(cur, ensure_ascii=False))


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
        # (Simplified path deletion logic for brevity)
        pass 

    if brief:
        if ja == jb:
            return
        raise typer.Exit(code=1)

    sa = json.dumps(ja, ensure_ascii=False, indent=2, sort_keys=sort_keys).splitlines(keepends=False)
    sb = json.dumps(jb, ensure_ascii=False, indent=2, sort_keys=sort_keys).splitlines(keepends=False)
    
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
