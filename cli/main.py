from __future__ import annotations
import json
import re
from typing import List, Any, Optional
from pathlib import Path
import sys
import typer
from rich import print
import difflib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json as _json
from jsonschema import Draft202012Validator

# Optional YAML support
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore
from app.compiler import (
    compile_text,
    compile_text_v2,
    optimize_ir,
    HEURISTIC_VERSION,
    HEURISTIC2_VERSION,
    generate_trace,
)
from app.emitters import (
    emit_system_prompt,
    emit_user_prompt,
    emit_plan,
    emit_expanded_prompt,
    emit_system_prompt_v2,
    emit_user_prompt_v2,
    emit_plan_v2,
    emit_expanded_prompt_v2,
)
from app import get_version
from app.plugins import describe_plugins
from app.templates import get_registry
from app.templates_manager import get_templates_manager
from app.validator import validate_prompt
from app.analytics import AnalyticsManager, create_record_from_ir
from app.history import get_history_manager
from app.export_import import get_export_import_manager
from app.favorites import get_favorites_manager
from app.snippets import get_snippets_manager
from app.collections import get_collections_manager
from app.search import get_search_engine, SearchResultType
from app.rag.simple_index import (
    ingest_paths,
    search,
    search_embed,
    search_hybrid,
    pack as pack_context,
    stats as rag_stats_fn,
    prune as rag_prune_fn,
    DEFAULT_DB_PATH,
)

app = typer.Typer(help="Prompt Compiler CLI")
rag_app = typer.Typer(help="Lightweight local RAG (SQLite FTS5)")
plugins_app = typer.Typer(help="Plugin utilities")
template_app = typer.Typer(help="Template management")
analytics_app = typer.Typer(help="Prompt analytics and metrics")
history_app = typer.Typer(help="Prompt history and quick access")
export_app = typer.Typer(help="Export and import data")
favorites_app = typer.Typer(help="Favorite prompts and bookmarks")
snippets_app = typer.Typer(help="Quick reusable prompt snippets")
collections_app = typer.Typer(help="Collections/workspaces for organizing prompts")
app.add_typer(rag_app, name="rag")
app.add_typer(plugins_app, name="plugins")
app.add_typer(template_app, name="template")
app.add_typer(analytics_app, name="analytics")
app.add_typer(history_app, name="history")
app.add_typer(export_app, name="export")
app.add_typer(favorites_app, name="favorites")
app.add_typer(snippets_app, name="snippets")
app.add_typer(collections_app, name="collections")


@app.command("edit")
def edit_prompt_command(
    prompt_id: str = typer.Argument(..., help="ID of the prompt to edit"),
    recompile: bool = typer.Option(False, "--recompile", "-r", help="Recompile after editing"),
):
    """
    Edit a prompt from history or favorites by ID.

    Opens an interactive editor to modify prompt text, metadata, tags, and more.
    Changes are saved back to history or favorites.

    Examples:
        promptc edit abc123
        promptc edit abc123 --recompile
    """
    from app.quick_edit import get_quick_editor
    from rich.console import Console

    console = Console()
    editor = get_quick_editor()

    # Preview the prompt first
    prompt, source = editor.find_prompt(prompt_id)

    if not prompt or not source:
        console.print(f"\n[red]❌ Prompt not found:[/red] {prompt_id}\n")
        raise typer.Exit(code=1)

    # Show preview
    editor.display_prompt_preview(prompt, source)

    # Edit the prompt
    success = editor.edit_prompt(prompt_id, recompile=recompile)

    if not success:
        raise typer.Exit(code=1)


@app.command("report")
def validation_report_command(
    prompts: List[str] = typer.Argument(None, help="Prompt texts or file paths to validate"),
    ids: List[str] = typer.Option(
        None, "--id", help="History/favorites IDs to validate (can be used multiple times)"
    ),
    format: str = typer.Option(
        "html", "--format", "-f", help="Report format: html, markdown, json"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    theme: str = typer.Option("light", "--theme", help="HTML theme: light or dark"),
    title: str = typer.Option("Prompt Validation Report", "--title", help="Report title"),
    no_charts: bool = typer.Option(False, "--no-charts", help="Disable charts in HTML"),
    no_recommendations: bool = typer.Option(
        False, "--no-recommendations", help="Disable recommendations"
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read prompts from stdin (one per line)"),
):
    """
    Generate validation report for one or multiple prompts.

    Supports HTML, Markdown, and JSON formats with detailed quality analysis,
    issue summaries, and recommendations.

    Examples:
        promptc report "Write a tutorial" --format html
        promptc report --id abc123 --id def456 --format markdown -o report.md
        promptc report prompt1.txt prompt2.txt --format json
        cat prompts.txt | promptc report --stdin --format html -o report.html
    """
    from rich.console import Console
    from app.validator import validate_prompt
    from app.compiler import compile_text_v2
    from app.report_generator import get_report_generator, ReportConfig
    from app.history import get_history_manager
    from app.favorites import get_favorites_manager

    console = Console()

    # Collect prompts
    prompt_texts = []

    if stdin:
        # Read from stdin
        try:
            prompt_texts = [line.strip() for line in sys.stdin if line.strip()]
        except Exception as e:
            console.print(f"[red]Error reading from stdin: {e}[/red]")
            raise typer.Exit(code=1)
    elif ids:
        # Load from history/favorites by ID
        history_mgr = get_history_manager()
        fav_mgr = get_favorites_manager()

        for prompt_id in ids:
            # Try history first
            entry = history_mgr.get_by_id(prompt_id)
            if entry:
                prompt_texts.append(entry.prompt_text)
                continue

            # Try favorites
            entry = fav_mgr.get_by_id(prompt_id)
            if entry:
                prompt_texts.append(entry.prompt_text)
                continue

            console.print(f"[yellow]Warning: ID not found: {prompt_id}[/yellow]")
    elif prompts:
        # Read from arguments (text or files)
        for prompt_arg in prompts:
            p = Path(prompt_arg)
            if p.exists() and p.is_file():
                try:
                    prompt_texts.append(p.read_text(encoding="utf-8"))
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not read {p}: {e}[/yellow]")
            else:
                prompt_texts.append(prompt_arg)
    else:
        console.print("[red]Error: Provide prompts, --id, or --stdin[/red]")
        raise typer.Exit(code=1)

    if not prompt_texts:
        console.print("[red]No prompts to validate[/red]")
        raise typer.Exit(code=1)

    # Validate all prompts
    console.print(f"[cyan]Validating {len(prompt_texts)} prompt(s)...[/cyan]")

    results = []
    for prompt_text in prompt_texts:
        try:
            ir2 = compile_text_v2(prompt_text)
            result = validate_prompt(ir2, prompt_text)
            results.append(result)
        except Exception as e:
            console.print(f"[red]Error validating prompt: {e}[/red]")
            raise typer.Exit(code=1)

    # Generate report
    config = ReportConfig(
        title=title,
        include_charts=not no_charts,
        include_recommendations=not no_recommendations,
        theme=theme,
    )

    generator = get_report_generator(config)

    fmt = format.lower()
    if fmt in {"html", "htm"}:
        report_content = generator.generate_html_report(results, prompt_texts)
    elif fmt in {"markdown", "md"}:
        report_content = generator.generate_markdown_report(results, prompt_texts)
    elif fmt == "json":
        import json

        report_dict = generator.generate_json_report(results, prompt_texts)
        report_content = json.dumps(report_dict, indent=2, ensure_ascii=False)
    else:
        console.print(f"[red]Unknown format: {fmt}. Use html, markdown, or json[/red]")
        raise typer.Exit(code=1)

    # Output
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_content, encoding="utf-8")
        console.print(f"\n[green]✓ Report saved to {output}[/green]")
    else:
        # Print to console
        typer.echo(report_content)

    # Show summary
    avg_score = sum(r.score.total for r in results) / len(results)
    total_issues = sum(r.errors + r.warnings for r in results)

    console.print("\n[bold cyan]Report Summary:[/bold cyan]")
    console.print(f"  Prompts analyzed: {len(results)}")
    console.print(f"  Average score: {avg_score:.1f}/100")
    console.print(f"  Total issues: {total_issues}")
    console.print(f"  Format: {fmt}")
    if output:
        console.print(f"  Saved to: {output}")


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
        data = ir.model_dump() if ir else ir2.model_dump()
        if trace and ir:
            data["trace"] = generate_trace(ir)
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
    ir_json = ir.model_dump() if ir else ir2.model_dump()
    if trace and ir:
        ir_json["trace"] = generate_trace(ir)
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


def _write_output(
    content: str, out: Path | None, out_dir: Path | None, default_name: str = "output.txt"
):
    target: Path
    if out:
        # Allow specifying full filename and ensure parent exists
        target = out
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        directory = out_dir or Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / default_name
    target.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    # Quiet for internal batch metrics; still show path when invoked directly
    if not getattr(_write_output, "_suppress_log", False):  # type: ignore
        print(f"[saved] {target}")


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


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    """Top-level CLI. Shows help when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def compile(
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
        v1=v1,
        render_v2=render_v2,
        out=out,
        out_dir=out_dir,
        fmt=format,
    )


@app.command()
def version():
    """Print package version."""
    print(get_version())


# --------------
# RAG subcommands
# --------------


@rag_app.command("index")
def rag_index(
    paths: List[Path] = typer.Argument(..., help="Files or folders to index"),
    ext: List[str] = typer.Option(None, "--ext", help="Extensions to include, e.g. .txt --ext .md"),
    db_path: Optional[Path] = typer.Option(
        None, "--db-path", help=f"SQLite DB path (default {DEFAULT_DB_PATH})"
    ),
    embed: bool = typer.Option(
        False, "--embed", help="Compute and store tiny deterministic embeddings"
    ),
    embed_dim: int = typer.Option(
        64, "--embed-dim", help="Embedding dimension when --embed is set"
    ),
):
    exts = ext or [".txt", ".md", ".py"]
    docs, chunks, secs = ingest_paths(
        [str(p) for p in paths],
        db_path=str(db_path) if db_path else None,
        exts=exts,
        embed=embed,
        embed_dim=embed_dim,
    )
    print(
        f"[indexed] docs={docs} chunks={chunks} in {int(secs*1000)} ms -> {(db_path or Path(DEFAULT_DB_PATH))}"
    )


@rag_app.command("query")
def rag_query(
    query: List[str] = typer.Argument(..., help="Query text"),
    k: int = typer.Option(5, "--k", help="Top-K results"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    method: str = typer.Option("fts", "--method", help="fts|embed|hybrid"),
    embed_dim: int = typer.Option(64, "--embed-dim", help="Embedding dimension for embed/hybrid"),
    alpha: float = typer.Option(0.5, "--alpha", help="Hybrid weighting factor"),
    min_score: Optional[float] = typer.Option(None, "--min-score", help="Minimum BM25 score (fts)"),
    min_sim: Optional[float] = typer.Option(
        None, "--min-sim", help="Minimum similarity (embed/hybrid)"
    ),
    min_hybrid: Optional[float] = typer.Option(
        None, "--min-hybrid", help="Minimum hybrid score (hybrid)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: md|yaml|json (default json)"
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
):
    q = " ".join(query)
    m = (method or "fts").lower()
    if m == "embed":
        res = search_embed(q, k=k, db_path=str(db_path) if db_path else None, embed_dim=embed_dim)
    elif m == "hybrid":
        res = search_hybrid(
            q, k=k, db_path=str(db_path) if db_path else None, embed_dim=embed_dim, alpha=alpha
        )
    else:
        res = search(q, k=k, db_path=str(db_path) if db_path else None)
    # Apply optional filters
    if min_score is not None:
        res = [r for r in res if r.get("score") is not None and r.get("score") >= min_score]
    if min_sim is not None:
        res = [r for r in res if r.get("similarity") is not None and r.get("similarity") >= min_sim]
    if min_hybrid is not None:
        res = [
            r
            for r in res
            if r.get("hybrid_score") is not None and r.get("hybrid_score") >= min_hybrid
        ]
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l or out or out_dir:
        # Decide serialization
        if fmt_l == "md":
            lines = [
                "# RAG Query\n",
                f"**query:** {q}",
                f"\n**method:** {m}  ",
                f"**k:** {k}",
                "\n\n## Results\n",
            ]
            for i, r in enumerate(res, 1):
                score_bits = []
                if "score" in r:
                    score_bits.append(f"score={r['score']:.3f}")
                if "similarity" in r:
                    score_bits.append(f"sim={r['similarity']:.3f}")
                if "hybrid_score" in r:
                    score_bits.append(f"hyb={r['hybrid_score']:.3f}")
                label = f"{Path(r['path']).name}#{r.get('chunk_index', 0)}"
                meta = f" ({', '.join(score_bits)})" if score_bits else ""
                snippet = r.get("snippet", "").replace("\r\n", "\n")
                lines.append(f"{i}. **{label}**{meta}\n\n   {snippet}\n")
            payload = "\n".join(lines)
            ext = "md"
        else:
            use_yaml = fmt_l in {"yaml", "yml"} and yaml is not None  # type: ignore
            payload = (
                yaml.safe_dump(res, sort_keys=False, allow_unicode=True)  # type: ignore
                if use_yaml
                else json.dumps(res, ensure_ascii=False, indent=2)
            )
            ext = "yaml" if use_yaml else "json"
        if out or out_dir:
            _write_output(payload, out, out_dir, default_name=f"rag_query.{ext}")
        else:
            typer.echo(payload)
    else:
        for i, r in enumerate(res, 1):
            meta = []
            if "similarity" in r:
                meta.append(f"sim={r['similarity']:.3f}")
            if "hybrid_score" in r:
                meta.append(f"hyb={r['hybrid_score']:.3f}")
            score = f"score={r['score']:.3f}" if "score" in r else ""
            print(
                f"{i}. {Path(r['path']).name} #{r['chunk_index']} {score} {' '.join(meta)}\n   {r['snippet']}"
            )


@rag_app.command("pack")
def rag_pack(
    query: List[str] = typer.Argument(..., help="Query to pack context for"),
    k: int = typer.Option(8, "--k", help="Top-K to retrieve before packing"),
    max_chars: int = typer.Option(4000, "--max-chars", help="Character budget"),
    max_tokens: Optional[int] = typer.Option(
        None, "--max-tokens", help="Approximate token budget (overrides chars)"
    ),
    token_ratio: float = typer.Option(4.0, "--token-ratio", help="Chars per token heuristic"),
    method: str = typer.Option("hybrid", "--method", help="fts|embed|hybrid"),
    embed_dim: int = typer.Option(64, "--embed-dim", help="Embedding dimension for embed/hybrid"),
    alpha: float = typer.Option(0.5, "--alpha", help="Hybrid weighting factor"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    json_out: bool = typer.Option(True, "--json", help="Print JSON (default true)"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: md|yaml|json (default json)"
    ),
    sources: str = typer.Option(
        "list",
        "--sources",
        help="In md format: none|list|full; list shows filenames, full shows chunk labels",
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
):
    q = " ".join(query)
    m = (method or "hybrid").lower()
    if m == "embed":
        res = search_embed(q, k=k, db_path=str(db_path) if db_path else None, embed_dim=embed_dim)
    elif m == "hybrid":
        res = search_hybrid(
            q, k=k, db_path=str(db_path) if db_path else None, embed_dim=embed_dim, alpha=alpha
        )
    else:
        res = search(q, k=k, db_path=str(db_path) if db_path else None)
    packed = pack_context(
        q, res, max_chars=max_chars, max_tokens=max_tokens, token_chars=token_ratio
    )
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l or out or out_dir:
        if fmt_l == "md":
            lines = [
                "# RAG Pack\n",
                f"**query:** {q}",
                f"\n**method:** {m}  ",
                f"**k:** {k}  ",
                f"**budget:** {'%d chars'%max_chars if not max_tokens else '%d tokens'%max_tokens}\n",
                "\n## Packed Context\n",
                "```\n" + (packed.get("packed", "") or "") + "\n```\n",
            ]
            if sources != "none":
                lines.append("\n## Sources\n")
                if sources == "full":
                    for i, r in enumerate(res, 1):
                        label = f"{r['path']}#chunk={r.get('chunk_index', 0)}"
                        lines.append(f"- {i}. {label}")
                else:  # list
                    for i, r in enumerate(res, 1):
                        label = f"{Path(r['path']).name}#{r.get('chunk_index', 0)}"
                        lines.append(f"- {i}. {label}")
            payload = "\n".join(lines)
            ext = "md"
        else:
            use_yaml = fmt_l in {"yaml", "yml"} and yaml is not None  # type: ignore
            payload = (
                yaml.safe_dump(packed, sort_keys=False, allow_unicode=True)  # type: ignore
                if use_yaml
                else json.dumps(packed, ensure_ascii=False, indent=2)
            )
            ext = "yaml" if use_yaml else "json"
        if out or out_dir:
            _write_output(payload, out, out_dir, default_name=f"rag_pack.{ext}")
        else:
            typer.echo(payload)
    else:
        print(packed.get("packed", ""))


@rag_app.command("stats")
def rag_stats(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: yaml|json (default json)"
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
):
    s = rag_stats_fn(db_path=str(db_path) if db_path else None)
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l or out or out_dir:
        use_yaml = fmt_l in {"yaml", "yml"} and yaml is not None  # type: ignore
        payload = (
            yaml.safe_dump(s, sort_keys=False, allow_unicode=True)  # type: ignore
            if use_yaml
            else json.dumps(s, ensure_ascii=False, indent=2)
        )
        if out or out_dir:
            ext = "yaml" if use_yaml else "json"
            _write_output(payload, out, out_dir, default_name=f"rag_stats.{ext}")
        else:
            typer.echo(payload)
    else:
        print(
            f"docs={s['docs']} chunks={s['chunks']} total_bytes={s['total_bytes']} avg_bytes={int(s['avg_bytes'])}"
        )
        if s.get("largest"):
            print("largest:")
            for it in s["largest"]:
                print(f" - {it['path']} ({it['size']})")


@rag_app.command("prune")
def rag_prune(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: yaml|json (default json)"
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
):
    r = rag_prune_fn(db_path=str(db_path) if db_path else None)
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l or out or out_dir:
        use_yaml = fmt_l in {"yaml", "yml"} and yaml is not None  # type: ignore
        payload = (
            yaml.safe_dump(r, sort_keys=False, allow_unicode=True)  # type: ignore
            if use_yaml
            else json.dumps(r, ensure_ascii=False, indent=2)
        )
        if out or out_dir:
            ext = "yaml" if use_yaml else "json"
            _write_output(payload, out, out_dir, default_name=f"rag_prune.{ext}")
        else:
            typer.echo(payload)
    else:
        print(f"removed_docs={r['removed_docs']} removed_chunks={r['removed_chunks']}")


# -----------------
# JSON path utility
# -----------------


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
    """Navigate JSON with simple path syntax including list indexes.

    Supported forms:
      metadata.ir_signature
      items[0].name
      nested.list[2].objects[0].value
    """
    try:
        data = _json.loads(file.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    token_re = re.compile(r"([A-Za-z0-9_\-]+)|\[(\d+)\]")
    # Split by dots but keep bracket expressions
    segments: list[str] = []
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
                segments.append(int(m.group(2)))  # type: ignore
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
            if isinstance(cur, list) and 0 <= seg < len(cur):  # type: ignore
                cur = cur[seg]  # type: ignore
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
        typer.echo(_json.dumps(cur, ensure_ascii=False))


# -----------------
# Diff utility
# -----------------


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
    try:
        ja = _json.loads(a.read_text(encoding="utf-8"))
        jb = _json.loads(b.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    # Optionally delete ignored paths
    if ignore_path:

        def _delete_path(root: Any, pth: str) -> None:
            token_re = re.compile(r"([A-Za-z0-9_\-]+)|\[(\d+)\]")
            parts: list[Any] = []
            for part in [p for p in pth.split(".") if p]:
                idx = 0
                while idx < len(part):
                    m = token_re.match(part, idx)
                    if not m:
                        return
                    if m.group(1):
                        parts.append(m.group(1))
                    else:
                        parts.append(int(m.group(2)))
                    idx = m.end()
            cur = root
            for i, seg in enumerate(parts):
                last = i == len(parts) - 1
                if isinstance(seg, str):
                    if not isinstance(cur, dict) or seg not in cur:
                        return
                    if last:
                        try:
                            del cur[seg]
                        except Exception:
                            pass
                        return
                    cur = cur[seg]
                else:
                    if not isinstance(cur, list) or not (0 <= seg < len(cur)):
                        return
                    if last:
                        try:
                            del cur[seg]
                        except Exception:
                            pass
                        return
                    cur = cur[seg]

        # Deep copy and mutate
        ja = _json.loads(_json.dumps(ja))
        jb = _json.loads(_json.dumps(jb))
        for pth in ignore_path:
            _delete_path(ja, pth)
            _delete_path(jb, pth)
    if brief:
        # Dict/list equality ignores key order; suitable for structural equality
        if ja == jb:
            return
        raise typer.Exit(code=1)
    sa = _json.dumps(ja, ensure_ascii=False, indent=2, sort_keys=sort_keys).splitlines(
        keepends=False
    )
    sb = _json.dumps(jb, ensure_ascii=False, indent=2, sort_keys=sort_keys).splitlines(
        keepends=False
    )
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


# -----------------
# Validate against schema(s)
# -----------------


@app.command("validate")
def validate(
    files: List[Path] = typer.Argument(..., help="JSON files to validate (v1 or v2)"),
):
    ok = 0
    fail = 0
    for p in files:
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            fail += 1
            typer.secho(f"[fail] {p}: {e}", fg=typer.colors.RED)
            continue
        # Choose schema by version
        v2 = isinstance(data, dict) and data.get("version") == "2.0"
        schema_path = Path("schema/ir_v2.schema.json" if v2 else "schema/ir.schema.json")
        try:
            schema = _json.loads(schema_path.read_text(encoding="utf-8"))
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


# -----------------
# Batch processing
# -----------------


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
    setattr(_write_output, "_suppress_log", True)  # type: ignore
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
                        obj = _json.loads(target_path.read_text(encoding="utf-8"))
                        line = _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
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
                    break
        else:
            with ThreadPoolExecutor(max_workers=jobs) as ex:
                futures = {ex.submit(process_file, src): src for src in files}
                for fut in as_completed(futures):
                    if fail_fast and fut.exception() is not None:
                        for other in futures:
                            other.cancel()
                        break

        if jsonl and jsonl_file:
            jsonl_file.close()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        avg_ms = elapsed_ms / max(1, len(files))
        print(
            f"[done] {len(files)} files -> outputs in {int(elapsed_ms)} ms (avg {avg_ms:.1f} ms) jobs={jobs}"
        )
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
                _json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
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
        if errors:
            for p, msg in errors[:5]:
                typer.secho(f"[error] {p}: {msg}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    finally:
        # Re-enable logging for other commands
        setattr(_write_output, "_suppress_log", False)  # type: ignore


# --------------
# Template subcommands (Legacy - kept for backward compatibility)
# --------------


@template_app.command("apply")
def template_apply(
    template_id: str = typer.Argument(..., help="Template ID to use"),
    var: List[str] = typer.Option(
        None, "--var", "-v", help="Variable in format name=value (can be used multiple times)"
    ),
    example: bool = typer.Option(False, "--example", "-e", help="Use example values from template"),
    compile_now: bool = typer.Option(
        True, "--compile/--no-compile", help="Compile the rendered prompt immediately"
    ),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Enable diagnostics mode"),
    json_only: bool = typer.Option(False, "--json-only", help="Output only IR JSON"),
    out: Optional[Path] = typer.Option(None, "--out", help="Save output to file"),
):
    """Apply a template with variable substitution and optionally compile it."""
    registry = get_registry()
    template = registry.get_template(template_id)

    if not template:
        typer.secho(f"Template '{template_id}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Parse variables
    variables: dict[str, str] = {}

    if example:
        variables.update(template.example_values)

    if var:
        for v in var:
            if "=" not in v:
                typer.secho(
                    f"Invalid variable format: {v} (expected name=value)", fg=typer.colors.RED
                )
                raise typer.Exit(code=1)
            name, value = v.split("=", 1)
            variables[name.strip()] = value.strip()

    # Check if we have all required variables
    missing = []
    for template_var in template.variables:
        if (
            template_var.required
            and template_var.name not in variables
            and not template_var.default
        ):
            missing.append(template_var.name)

    if missing:
        typer.secho(f"Missing required variables: {', '.join(missing)}", fg=typer.colors.RED)
        typer.echo(f"\nRun 'promptc template show {template_id}' to see variable details.")
        raise typer.Exit(code=1)

    # Render template
    try:
        rendered = template.render(variables)
    except ValueError as e:
        typer.secho(f"Template rendering failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not compile_now:
        typer.echo(rendered)
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
            print(f"[saved] {out}")
        return

    # Compile the rendered prompt
    _run_compile(
        rendered,
        diagnostics=diagnostics,
        json_only=json_only,
        quiet=False,
        persona=None,
        trace=False,
        v1=False,
        render_v2=False,
        out=out,
        out_dir=None,
        fmt=None,
    )


@app.command("validate-prompt")
def validate_prompt_command(
    text: List[str] = typer.Argument(None, help="Prompt text to validate"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read prompt from file"
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin"),
    show_suggestions: bool = typer.Option(
        True, "--suggestions/--no-suggestions", help="Show improvement suggestions"
    ),
    show_strengths: bool = typer.Option(
        True, "--strengths/--no-strengths", help="Show prompt strengths"
    ),
    min_score: Optional[float] = typer.Option(
        None, "--min-score", help="Fail if score below threshold (0-100)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
):
    """Validate a prompt and get quality score with suggestions.

    Examples:
        promptc validate-prompt "Write a tutorial about Python"
        promptc validate-prompt --from-file prompt.txt --min-score 70
        cat prompt.txt | promptc validate-prompt --stdin --json
    """
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

    # Compile to IR v2
    ir2 = compile_text_v2(full_text)

    # Validate
    result = validate_prompt(ir2, original_text=full_text)

    # Prepare output
    if json_out:
        output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        if out:
            out.write_text(output, encoding="utf-8")
            typer.echo(f"Validation report saved to {out}")
        else:
            typer.echo(output)
    else:
        # Rich formatted output
        lines = []
        lines.append("\n[bold cyan]═══ Prompt Quality Report ═══[/bold cyan]\n")

        # Score section
        score = result.score
        total_color = "green" if score.total >= 80 else "yellow" if score.total >= 60 else "red"
        lines.append(
            f"[bold]Overall Score:[/bold] [{total_color}]{score.total:.1f}/100[/{total_color}]\n"
        )
        lines.append("[bold]Breakdown:[/bold]")
        lines.append(f"  • Clarity:       {score.clarity:.1f}/100")
        lines.append(f"  • Specificity:   {score.specificity:.1f}/100")
        lines.append(f"  • Completeness:  {score.completeness:.1f}/100")
        lines.append(f"  • Consistency:   {score.consistency:.1f}/100\n")

        # Issues section
        if result.issues:
            lines.append(
                f"[bold]Issues Found:[/bold] {result.errors} errors, {result.warnings} warnings, {result.info} info\n"
            )
            for issue in result.issues:
                severity_color = {"error": "red", "warning": "yellow", "info": "blue"}[
                    issue.severity
                ]
                icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}[issue.severity]
                lines.append(
                    f"[{severity_color}]{icon} {issue.severity.upper()}[/{severity_color}] ({issue.category})"
                )
                lines.append(f"  {issue.message}")
                if show_suggestions:
                    lines.append(f"  [dim]💡 {issue.suggestion}[/dim]")
                if issue.field:
                    lines.append(f"  [dim]   Field: {issue.field}[/dim]")
                lines.append("")
        else:
            lines.append("[bold green]✓ No issues found![/bold green]\n")

        # Strengths section
        if show_strengths and result.strengths:
            lines.append("[bold green]Strengths:[/bold green]")
            for strength in result.strengths:
                lines.append(f"  [green]✓[/green] {strength}")
            lines.append("")

        # Recommendation
        if score.total >= 80:
            lines.append("[bold green]✓ Excellent prompt! Ready to use.[/bold green]")
        elif score.total >= 60:
            lines.append("[bold yellow]⚠ Good prompt, but could be improved.[/bold yellow]")
        else:
            lines.append("[bold red]✗ Prompt needs significant improvement.[/bold red]")

        output = "\n".join(lines)
        if out:
            # Remove Rich markup for file output
            import re

            clean_output = re.sub(r"\[/?[a-z0-9 ]+\]", "", output)
            out.write_text(clean_output, encoding="utf-8")
            typer.echo(f"Validation report saved to {out}")
        else:
            print(output)

    # Exit with error code if below min_score
    if min_score is not None and result.score.total < min_score:
        typer.echo(f"\nValidation failed: Score {result.score.total:.1f} < {min_score}", err=True)
        raise typer.Exit(1)


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
    """Automatically fix prompt based on validation issues.

    Examples:
        promptc fix "do something with stuff"
        promptc fix --from-file prompt.txt --apply
        promptc fix --stdin --target-score 80 --out fixed.txt
    """
    from app.autofix import auto_fix_prompt, explain_fixes

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
        from rich.console import Console
        from rich.panel import Panel

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
    """
    Compare two prompts side by side.

    Shows validation scores, strengths/weaknesses, IR differences,
    and recommendation on which prompt is better.

    Examples:
        promptc compare "Write a story" "Write a creative story about dragons"
        promptc compare prompt1.txt prompt2.txt --label-a "Version 1" --label-b "Version 2"
        promptc compare prompt1.txt prompt2.txt --json -o comparison.json
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.markdown import Markdown
    from app.compare import compare_prompts

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

    # Strengths/Issues comparison
    # Prompt A panel
    a_content = []
    if result.validation_a.strengths:
        a_content.append("[bold green]✓ Strengths:[/bold green]")
        for strength in result.validation_a.strengths[:3]:
            a_content.append(f"  • {strength}")

    if result.validation_a.issues:
        high_issues = [i for i in result.validation_a.issues if i.severity == "high"]
        if high_issues:
            a_content.append("\n[bold red]✗ Issues:[/bold red]")
            for issue in high_issues[:3]:
                a_content.append(f"  • {issue.message}")

    panel_a = Panel(
        "\n".join(a_content) if a_content else "[dim]No notable findings[/dim]",
        title=f"[bold]{label_a}[/bold]",
        border_style="blue",
        padding=(1, 2),
    )

    # Prompt B panel
    b_content = []
    if result.validation_b.strengths:
        b_content.append("[bold green]✓ Strengths:[/bold green]")
        for strength in result.validation_b.strengths[:3]:
            b_content.append(f"  • {strength}")

    if result.validation_b.issues:
        high_issues = [i for i in result.validation_b.issues if i.severity == "high"]
        if high_issues:
            b_content.append("\n[bold red]✗ Issues:[/bold red]")
            for issue in high_issues[:3]:
                b_content.append(f"  • {issue.message}")

    panel_b = Panel(
        "\n".join(b_content) if b_content else "[dim]No notable findings[/dim]",
        title=f"[bold]{label_b}[/bold]",
        border_style="blue",
        padding=(1, 2),
    )

    console.print("\n")
    console.print(Columns([panel_a, panel_b], equal=True, expand=True))

    # IR Changes
    if result.ir_changes:
        console.print("\n[bold magenta]🔄 IR Changes:[/bold magenta]")
        changes_table = Table(show_header=True, header_style="bold cyan")
        changes_table.add_column("Field", style="cyan", width=20)
        changes_table.add_column("Change Type", style="yellow", width=15)
        changes_table.add_column("Details", style="white")

        for change in result.ir_changes:
            field = change["field"]
            change_type = change["change_type"]

            if change_type == "modified":
                details = f"'{change.get('from', '')}' → '{change.get('to', '')}'"
            elif change_type == "added":
                details = f"Added: {', '.join(map(str, change.get('values', [])))}"
            elif change_type == "removed":
                details = f"Removed: {', '.join(map(str, change.get('values', [])))}"
            elif change_type == "count_changed":
                details = f"Count: {change.get('from_count', 0)} → {change.get('to_count', 0)}"
            else:
                details = str(change)

            changes_table.add_row(field, change_type, details)

        console.print(changes_table)
    else:
        console.print("\n[dim]No significant IR changes detected[/dim]")

    # IR Diff (if requested)
    if show_diff and result.ir_diff:
        console.print("\n[bold magenta]📝 Full IR Diff:[/bold magenta]")
        # Color-code diff lines
        diff_lines = result.ir_diff.split("\n")
        for line in diff_lines[:50]:  # Limit to first 50 lines
            if line.startswith("+") and not line.startswith("+++"):
                console.print(f"[green]{line}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                console.print(f"[red]{line}[/red]")
            elif line.startswith("@@"):
                console.print(f"[cyan]{line}[/cyan]")
            else:
                console.print(f"[dim]{line}[/dim]")

        if len(diff_lines) > 50:
            console.print(f"[dim]... ({len(diff_lines) - 50} more lines)[/dim]")

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
        if out.suffix.lower() in {".yaml", ".yml"}:
            if yaml is not None:
                output_text = yaml.safe_dump(output_data, sort_keys=False, allow_unicode=True)
            else:
                typer.secho("PyYAML not installed; saving as JSON", fg=typer.colors.YELLOW)
                output_text = json.dumps(output_data, ensure_ascii=False, indent=2)
        else:
            output_text = json.dumps(output_data, ensure_ascii=False, indent=2)

        out.write_text(output_text, encoding="utf-8")
        typer.echo(f"\n✓ Comparison saved to {out}")


# ============================================================================
# Analytics Commands
# ============================================================================


@analytics_app.command("record")
def analytics_record(
    prompt: Path = typer.Argument(..., help="Path to prompt file"),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Run validation and include scores"
    ),
):
    """
    Record a prompt compilation in analytics database
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if not prompt.exists():
        typer.secho(f"Error: File not found: {prompt}", fg=typer.colors.RED)
        raise typer.Exit(1)

    prompt_text = prompt.read_text(encoding="utf-8")

    with console.status("[cyan]Compiling prompt..."):
        ir = compile_text_v2(prompt_text)

    validation_result = None
    if validate:
        with console.status("[cyan]Validating prompt..."):
            from app.validator import validate_prompt as validator

            validation_result = validator(ir, prompt_text)

    # Create record
    record = create_record_from_ir(prompt_text, ir.model_dump(), validation_result)

    # Save to analytics
    manager = AnalyticsManager()
    record_id = manager.record_prompt(record)

    console.print(
        Panel(
            f"[green]✓ Recorded successfully[/green]\n\n"
            f"Record ID: [cyan]{record_id}[/cyan]\n"
            f"Score: [yellow]{record.validation_score:.1f}[/yellow]\n"
            f"Domain: {record.domain}\n"
            f"Language: {record.language}\n"
            f"Issues: {record.issues_count}",
            title="[bold]Analytics Record[/bold]",
            border_style="green",
        )
    )


@analytics_app.command("summary")
def analytics_summary(
    days: int = typer.Option(30, help="Number of days to analyze"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show analytics summary for a time period
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing data..."):
        summary = manager.get_summary(days=days, domain=domain, persona=persona)

    if json_output:
        from dataclasses import asdict

        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
        return

    # Display rich formatted summary
    console.print(f"\n[bold cyan]Analytics Summary[/bold cyan] [dim](Last {days} days)[/dim]\n")

    # Overview table
    overview = Table(show_header=False, box=None, padding=(0, 2))
    overview.add_column("Metric", style="bold")
    overview.add_column("Value")

    overview.add_row("Total Prompts", str(summary.total_prompts))
    overview.add_row(
        "Avg Score", f"[yellow]{summary.avg_score:.1f}[/yellow] ± {summary.score_std:.1f}"
    )
    overview.add_row("Score Range", f"{summary.min_score:.1f} → {summary.max_score:.1f}")
    overview.add_row("Avg Issues", f"{summary.avg_issues:.1f}")
    overview.add_row("Avg Length", f"{summary.avg_prompt_length} chars")

    if summary.improvement_rate != 0:
        color = "green" if summary.improvement_rate > 0 else "red"
        arrow = "↑" if summary.improvement_rate > 0 else "↓"
        overview.add_row(
            "Improvement", f"[{color}]{arrow} {abs(summary.improvement_rate):.1f}%[/{color}]"
        )

    console.print(Panel(overview, title="[bold]Overview[/bold]", border_style="cyan"))

    # Top domains
    if summary.top_domains:
        console.print("\n[bold]Top Domains:[/bold]")
        domains_table = Table(show_header=True, box=None, padding=(0, 2))
        domains_table.add_column("Domain", style="cyan")
        domains_table.add_column("Count", justify="right")
        for domain, count in summary.top_domains:
            domains_table.add_row(domain, str(count))
        console.print(domains_table)

        if summary.most_improved_domain:
            console.print(f"  [green]Most Improved:[/green] {summary.most_improved_domain}")

    # Top personas
    if summary.top_personas:
        console.print("\n[bold]Top Personas:[/bold]")
        personas_table = Table(show_header=True, box=None, padding=(0, 2))
        personas_table.add_column("Persona", style="magenta")
        personas_table.add_column("Count", justify="right")
        for persona, count in summary.top_personas:
            personas_table.add_row(persona, str(count))
        console.print(personas_table)

    # Language distribution
    if summary.language_distribution:
        console.print("\n[bold]Languages:[/bold]")
        for lang, count in summary.language_distribution.items():
            console.print(f"  {lang}: {count}")

    # Top intents
    if summary.top_intents:
        console.print("\n[bold]Top Intents:[/bold]")
        intents_table = Table(show_header=True, box=None, padding=(0, 2))
        intents_table.add_column("Intent", style="yellow")
        intents_table.add_column("Count", justify="right")
        for intent, count in summary.top_intents[:5]:
            intents_table.add_row(intent, str(count))
        console.print(intents_table)


@analytics_app.command("trends")
def analytics_trends(
    days: int = typer.Option(30, help="Number of days to analyze"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show score trends over time
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing trends..."):
        trends = manager.get_score_trends(days=days)

    if not trends:
        console.print("[yellow]No data available for the specified period[/yellow]")
        return

    if json_output:
        print(json.dumps(trends, ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Score Trends[/bold cyan] [dim](Last {days} days)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Avg Score", justify="right", style="yellow")
    table.add_column("Range", justify="right")
    table.add_column("Count", justify="right", style="dim")
    table.add_column("Trend", justify="center")

    prev_score = None
    for entry in trends:
        # Trend indicator
        if prev_score is not None:
            diff = entry["avg_score"] - prev_score
            if diff > 0:
                trend = f"[green]↑ +{diff:.1f}[/green]"
            elif diff < 0:
                trend = f"[red]↓ {diff:.1f}[/red]"
            else:
                trend = "[dim]→ 0.0[/dim]"
        else:
            trend = "[dim]—[/dim]"

        table.add_row(
            entry["date"],
            f"{entry['avg_score']:.1f}",
            f"{entry['min_score']:.1f}–{entry['max_score']:.1f}",
            str(entry["count"]),
            trend,
        )

        prev_score = entry["avg_score"]

    console.print(table)


@analytics_app.command("domains")
def analytics_domains(
    days: int = typer.Option(30, help="Number of days to analyze"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show domain breakdown and statistics
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing domains..."):
        domain_stats = manager.get_domain_breakdown(days=days)

    if not domain_stats:
        console.print("[yellow]No data available[/yellow]")
        return

    if json_output:
        print(json.dumps(domain_stats, ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Domain Breakdown[/bold cyan] [dim](Last {days} days)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("Domain", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Avg Score", justify="right", style="yellow")
    table.add_column("Score Range", justify="right")
    table.add_column("Avg Issues", justify="right", style="red")

    # Sort by count
    sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    for domain, stats in sorted_domains:
        table.add_row(
            domain,
            str(stats["count"]),
            f"{stats['avg_score']:.1f}",
            f"{stats['min_score']:.1f}–{stats['max_score']:.1f}",
            f"{stats['avg_issues']:.1f}",
        )

    console.print(table)


@analytics_app.command("list")
def analytics_list(
    limit: int = typer.Option(20, help="Number of records to show"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    min_score: Optional[float] = typer.Option(None, help="Minimum score"),
    max_score: Optional[float] = typer.Option(None, help="Maximum score"),
):
    """
    List recent prompt records
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    manager = AnalyticsManager()

    records = manager.get_records(
        limit=limit, domain=domain, persona=persona, min_score=min_score, max_score=max_score
    )

    if not records:
        console.print("[yellow]No records found[/yellow]")
        return

    console.print(f"\n[bold cyan]Recent Prompts[/bold cyan] [dim](Last {limit})[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Score", justify="right", style="yellow", width=6)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Language", width=4)
    table.add_column("Issues", justify="right", style="red", width=6)
    table.add_column("Preview", style="dim", width=40)

    for record in records:
        # Format date
        date_str = record.timestamp[:10]  # YYYY-MM-DD

        # Truncate preview
        preview = record.prompt_text.replace("\n", " ")[:50]
        if len(record.prompt_text) > 50:
            preview += "..."

        # Color code score
        score_str = f"{record.validation_score:.1f}"
        if record.validation_score >= 80:
            score_style = "green"
        elif record.validation_score >= 60:
            score_style = "yellow"
        else:
            score_style = "red"

        table.add_row(
            str(record.id),
            date_str,
            f"[{score_style}]{score_str}[/{score_style}]",
            record.domain,
            record.language.upper(),
            str(record.issues_count),
            preview,
        )

    console.print(table)


@analytics_app.command("stats")
def analytics_stats():
    """
    Show overall database statistics
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    manager = AnalyticsManager()
    stats = manager.get_stats()

    info = (
        f"Total Records: [cyan]{stats['total_records']}[/cyan]\n"
        f"Overall Avg Score: [yellow]{stats['overall_avg_score']:.1f}[/yellow]\n"
        f"First Record: [dim]{stats['first_record'] or 'N/A'}[/dim]\n"
        f"Last Record: [dim]{stats['last_record'] or 'N/A'}[/dim]\n"
        f"Database: [dim]{stats['database_path']}[/dim]"
    )

    console.print(
        Panel(
            info, title="[bold cyan]Analytics Database Statistics[/bold cyan]", border_style="cyan"
        )
    )


@analytics_app.command("clean")
def analytics_clean(
    days: int = typer.Option(90, help="Delete records older than N days"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """
    Delete old analytics records
    """
    from rich.console import Console

    console = Console()

    if not force:
        confirm = typer.confirm(f"Delete all records older than {days} days?")
        if not confirm:
            typer.echo("Cancelled")
            raise typer.Exit()

    manager = AnalyticsManager()

    with console.status("[cyan]Cleaning old records..."):
        deleted = manager.clear_old_records(days=days)

    console.print(f"[green]✓ Deleted {deleted} old records[/green]")


# ============================================================================
# History Commands
# ============================================================================


@history_app.command("list")
def history_list(
    limit: int = typer.Option(10, help="Number of entries to show"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    List recent prompt history
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    history_mgr = get_history_manager()

    # Get entries
    if domain:
        entries = history_mgr.get_by_domain(domain, limit=limit)
    else:
        entries = history_mgr.get_recent(limit=limit)

    if not entries:
        console.print("[yellow]No history entries found[/yellow]")
        return

    if json_output:
        import json as _json

        print(_json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Prompt History[/bold cyan] [dim](Last {limit})[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Score", justify="right", style="yellow", width=6)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Lang", width=4)
    table.add_column("Prompt", style="dim", width=50)

    for entry in entries:
        # Format date
        date_str = entry.timestamp[:10]

        # Truncate prompt
        prompt_preview = entry.prompt_text.replace("\n", " ")[:50]
        if len(entry.prompt_text) > 50:
            prompt_preview += "..."

        # Score color
        if entry.score >= 80:
            score_style = "green"
        elif entry.score >= 60:
            score_style = "yellow"
        else:
            score_style = "red" if entry.score > 0 else "dim"

        score_str = f"{entry.score:.1f}" if entry.score > 0 else "—"

        table.add_row(
            entry.id[:8],
            date_str,
            f"[{score_style}]{score_str}[/{score_style}]",
            entry.domain,
            entry.language.upper(),
            prompt_preview,
        )

    console.print(table)


@history_app.command("search")
def history_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, help="Maximum results"),
):
    """
    Search prompt history
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    history_mgr = get_history_manager()

    entries = history_mgr.search(query, limit=limit)

    if not entries:
        console.print(f"[yellow]No matches found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold cyan]Search Results[/bold cyan] [dim]({len(entries)} matches)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Prompt", style="white", width=60)

    for entry in entries:
        date_str = entry.timestamp[:10]
        prompt_preview = entry.prompt_text.replace("\n", " ")[:60]
        if len(entry.prompt_text) > 60:
            prompt_preview += "..."

        # Highlight query in preview
        import re

        highlighted = re.sub(
            f"({re.escape(query)})",
            r"[bold yellow]\1[/bold yellow]",
            prompt_preview,
            flags=re.IGNORECASE,
        )

        table.add_row(entry.id[:8], date_str, entry.domain, highlighted)

    console.print(table)


@history_app.command("show")
def history_show(entry_id: str = typer.Argument(..., help="Entry ID")):
    """
    Show full details of a history entry
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    history_mgr = get_history_manager()

    entry = history_mgr.get_by_id(entry_id)

    if not entry:
        console.print(f"[red]Entry '{entry_id}' not found[/red]")
        raise typer.Exit(1)

    # Display details
    console.print(f"\n[bold]Entry {entry.id}[/bold]\n")

    info = (
        f"[cyan]Date:[/cyan] {entry.timestamp}\n"
        f"[cyan]Domain:[/cyan] {entry.domain}\n"
        f"[cyan]Language:[/cyan] {entry.language}\n"
        f"[cyan]IR Version:[/cyan] {entry.ir_version}\n"
    )

    if entry.score > 0:
        score_color = "green" if entry.score >= 80 else "yellow"
        info += f"[cyan]Score:[/cyan] [{score_color}]{entry.score:.1f}[/{score_color}]\n"

    console.print(Panel(info, title="[bold]Info[/bold]", border_style="blue"))

    # Prompt text
    console.print("\n[bold]Prompt:[/bold]")
    console.print(Panel(entry.prompt_text, border_style="green"))


@history_app.command("stats")
def history_stats():
    """
    Show history statistics
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    history_mgr = get_history_manager()

    stats = history_mgr.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]No history entries[/yellow]")
        return

    info = f"[cyan]Total Entries:[/cyan] {stats['total']}\n"
    info += f"[cyan]Avg Score:[/cyan] [yellow]{stats['avg_score']:.1f}[/yellow]\n"
    info += f"[cyan]Oldest:[/cyan] {stats['oldest'][:10] if stats['oldest'] else 'N/A'}\n"
    info += f"[cyan]Newest:[/cyan] {stats['newest'][:10] if stats['newest'] else 'N/A'}\n\n"

    info += "[bold]Domains:[/bold]\n"
    for domain, count in stats["domains"].items():
        info += f"  {domain}: {count}\n"

    info += "\n[bold]Languages:[/bold]\n"
    for lang, count in stats["languages"].items():
        info += f"  {lang.upper()}: {count}\n"

    console.print(
        Panel(info, title="[bold cyan]History Statistics[/bold cyan]", border_style="cyan")
    )


@history_app.command("clear")
def history_clear(force: bool = typer.Option(False, "--force", help="Skip confirmation")):
    """
    Clear all history
    """
    from rich.console import Console

    console = Console()

    if not force:
        confirm = typer.confirm("Clear all history?")
        if not confirm:
            typer.echo("Cancelled")
            raise typer.Exit()

    history_mgr = get_history_manager()
    history_mgr.clear()

    console.print("[green]✓ History cleared[/green]")


# ============================================================================
# Export/Import Commands
# ============================================================================


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

File: {result['file']}
Format: {result['format']}
Type: {result['data_type']}
Analytics: {result['analytics_count']} records
History: {result['history_count']} entries
Export Date: {result['export_date']}"""

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

File: {result['file']}
Format: {result['format']}
Mode: {mode}
Analytics: {result['analytics_imported']} records imported
History: {result['history_imported']} entries imported"""

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
    from datetime import datetime

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

Location: {result['file']}
Format: {result['format']}
Analytics: {result['analytics_count']} records
History: {result['history_count']} entries
Backup Date: {result['export_date']}"""

        console.print(
            Panel(info, title="[bold cyan]Backup Complete[/bold cyan]", border_style="cyan")
        )

    except Exception as e:
        console.print(f"[bold red]✗ Backup failed:[/bold red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Template Management Commands
# ============================================================================


@template_app.command("list")
def template_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search in name/description"),
    show_details: bool = typer.Option(False, "--details", "-d", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all available templates."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    manager = get_templates_manager()

    try:
        templates = manager.list_templates(category=category, tag=tag, search=search)

        if not templates:
            console.print("[yellow]No templates found matching criteria[/yellow]")
            return

        if json_output:
            output = [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "tags": t.tags,
                    "variables": [v.name for v in t.variables],
                    "author": t.author,
                }
                for t in templates
            ]
            print(json.dumps(output, indent=2, ensure_ascii=False))
            return

        if show_details:
            for template in templates:
                stats = manager.get_stats(template.id)
                var_info = ", ".join(
                    [f"{v.name}{'*' if v.required else ''}" for v in template.variables]
                )

                info = f"""[bold]ID:[/bold] {template.id}
[bold]Category:[/bold] {template.category}
[bold]Variables:[/bold] {var_info or 'None'}
[bold]Tags:[/bold] {', '.join(template.tags) or 'None'}
[bold]Author:[/bold] {template.author or 'Unknown'}
[bold]Uses:[/bold] {stats['use_count']}
[bold]Description:[/bold] {template.description}"""

                console.print(
                    Panel(info, title=f"[cyan]{template.name}[/cyan]", border_style="cyan")
                )
                console.print()
        else:
            table = Table(title="Available Templates", show_header=True, header_style="bold cyan")
            table.add_column("ID", style="cyan", width=20)
            table.add_column("Name", style="green", width=30)
            table.add_column("Category", style="yellow", width=15)
            table.add_column("Variables", style="magenta", width=10)
            table.add_column("Tags", style="blue", width=20)

            for template in templates:
                var_count = len(template.variables)
                tags_str = ", ".join(template.tags[:3])
                if len(template.tags) > 3:
                    tags_str += "..."

                table.add_row(
                    template.id,
                    template.name[:28] + "..." if len(template.name) > 28 else template.name,
                    template.category,
                    str(var_count),
                    tags_str,
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(templates)} templates[/dim]")
            console.print("[dim]Use --details to see full information[/dim]")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@template_app.command("show")
def template_show(
    template_id: str = typer.Argument(..., help="Template ID to show"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show template text preview"),
    validate: bool = typer.Option(False, "--validate", "-v", help="Validate template"),
):
    """Show detailed information about a template."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table

    console = Console()
    manager = get_templates_manager()

    template = manager.get_template(template_id)
    if not template:
        console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    # Basic info
    stats = manager.get_stats(template_id)
    info = f"""[bold]ID:[/bold] {template.id}
[bold]Name:[/bold] {template.name}
[bold]Category:[/bold] {template.category}
[bold]Description:[/bold] {template.description}
[bold]Tags:[/bold] {', '.join(template.tags) or 'None'}
[bold]Author:[/bold] {template.author or 'Unknown'}
[bold]Version:[/bold] {template.version}
[bold]Uses:[/bold] {stats['use_count']}
[bold]Last Used:[/bold] {stats.get('last_used', 'Never')}"""

    console.print(
        Panel(info, title="[bold cyan]Template Information[/bold cyan]", border_style="cyan")
    )

    # Variables
    if template.variables:
        var_table = Table(title="Variables", show_header=True, header_style="bold yellow")
        var_table.add_column("Name", style="cyan")
        var_table.add_column("Required", style="magenta")
        var_table.add_column("Default", style="green")
        var_table.add_column("Description", style="white")

        for var in template.variables:
            var_table.add_row(
                var.name,
                "✓" if var.required else "✗",
                var.default or "-",
                var.description,
            )

        console.print(var_table)

    # Example values
    if template.example_values:
        console.print("\n[bold yellow]Example Values:[/bold yellow]")
        for key, value in template.example_values.items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")

    # Preview
    if preview:
        console.print("\n[bold yellow]Template Text:[/bold yellow]")
        syntax = Syntax(template.template_text, "markdown", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, border_style="yellow"))

    # Validation
    if validate:
        validation = manager.validate_template(template_id)
        console.print("\n[bold yellow]Validation Results:[/bold yellow]")

        if validation["valid"]:
            console.print("[green]✓ Template is valid[/green]")
        else:
            console.print("[red]✗ Template has issues:[/red]")
            for issue in validation["issues"]:
                console.print(f"  • {issue}")

        if validation.get("required_variables"):
            console.print(
                f"\n[dim]Required variables: {', '.join(validation['required_variables'])}[/dim]"
            )


@template_app.command("create")
def template_create(
    template_id: str = typer.Argument(..., help="Unique template ID"),
    name: str = typer.Option(..., "--name", "-n", help="Template name"),
    description: str = typer.Option(..., "--description", "-d", help="Template description"),
    category: str = typer.Option(..., "--category", "-c", help="Template category"),
    template_text: str = typer.Option(..., "--text", "-t", help="Template text with {{variables}}"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Author name"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read template text from file"
    ),
):
    """Create a new custom template."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_templates_manager()

    try:
        # Read template text from file if provided
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            template_text = from_file.read_text(encoding="utf-8")

        # Parse tags
        tag_list = [t.strip() for t in tags.split(",")] if tags else []

        # Extract variables from template text
        import re

        placeholders = set(re.findall(r"\{\{(\w+)\}\}", template_text))

        if not placeholders:
            console.print("[yellow]⚠ Warning: No {{variables}} found in template text[/yellow]")

        # Create variable definitions
        variables = []
        for var_name in sorted(placeholders):
            variables.append(
                {
                    "name": var_name,
                    "description": f"Value for {var_name}",
                    "required": True,
                }
            )

        # Create template
        template = manager.create_template(
            template_id=template_id,
            name=name,
            description=description,
            category=category,
            template_text=template_text,
            variables=variables,
            tags=tag_list,
            author=author,
        )

        info = f"""[bold]ID:[/bold] {template.id}
[bold]Name:[/bold] {template.name}
[bold]Category:[/bold] {template.category}
[bold]Variables:[/bold] {', '.join([v.name for v in template.variables])}
[bold]Tags:[/bold] {', '.join(template.tags) or 'None'}"""

        console.print(
            Panel(info, title="[bold green]✓ Template Created[/bold green]", border_style="green")
        )
        console.print(f"\n[dim]Use 'promptc template show {template_id}' to view details[/dim]")

    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]✗ Error creating template:[/bold red] {e}")
        raise typer.Exit(code=1)


@template_app.command("use")
def template_use(
    template_id: str = typer.Argument(..., help="Template ID to use"),
    variables: Optional[List[str]] = typer.Option(
        None, "--var", "-v", help="Variable in key=value format"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive variable input"
    ),
    compile_result: bool = typer.Option(
        False, "--compile", "-c", help="Compile the rendered template"
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
):
    """Use a template by providing variable values."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()
    manager = get_templates_manager()

    template = manager.get_template(template_id)
    if not template:
        console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    try:
        # Parse variables
        var_dict = {}
        if variables:
            for var_str in variables:
                if "=" not in var_str:
                    console.print(f"[bold red]✗ Invalid variable format:[/bold red] {var_str}")
                    console.print("[dim]Use: --var key=value[/dim]")
                    raise typer.Exit(code=1)
                key, value = var_str.split("=", 1)
                var_dict[key.strip()] = value.strip()

        # Interactive mode
        if interactive:
            console.print(f"[bold cyan]Template:[/bold cyan] {template.name}\n")
            for var in template.variables:
                default = var_dict.get(var.name) or var.default
                prompt_text = f"{var.name}"
                if var.description:
                    prompt_text += f" ({var.description})"
                if default:
                    prompt_text += f" [{default}]"

                value = Prompt.ask(prompt_text, default=default or "")
                if value:
                    var_dict[var.name] = value

        # Use example values for missing non-required variables
        for var in template.variables:
            if var.name not in var_dict and not var.required:
                if var.name in template.example_values:
                    var_dict[var.name] = template.example_values[var.name]

        # Render template
        rendered = manager.use_template(template_id, var_dict)
        if rendered is None:
            console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
            raise typer.Exit(code=1)

        # Show result
        console.print(
            Panel(
                rendered, title="[bold green]Rendered Template[/bold green]", border_style="green"
            )
        )

        # Copy to clipboard
        if copy:
            try:
                import pyperclip

                pyperclip.copy(rendered)
                console.print("\n[green]✓ Copied to clipboard[/green]")
            except ImportError:
                console.print(
                    "\n[yellow]⚠ pyperclip not installed - cannot copy to clipboard[/yellow]"
                )

        # Compile result
        if compile_result:
            console.print("\n[bold cyan]Compiling rendered template...[/bold cyan]")
            ir2 = compile_text_v2(rendered)
            console.print("\n[bold yellow]Compiled IR:[/bold yellow]")
            print(json.dumps(ir2.model_dump(), indent=2, ensure_ascii=False))

    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]✗ Error using template:[/bold red] {e}")
        raise typer.Exit(code=1)


@template_app.command("delete")
def template_delete(
    template_id: str = typer.Argument(..., help="Template ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a custom template."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    manager = get_templates_manager()

    template = manager.get_template(template_id)
    if not template:
        console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    if not force:
        confirm = Confirm.ask(f"Delete template '{template.name}' ({template_id})?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    success = manager.delete_template(template_id, user_only=True)
    if success:
        console.print(f"[green]✓ Template '{template_id}' deleted[/green]")
    else:
        console.print("[bold red]✗ Failed to delete template (may be built-in)[/bold red]")
        raise typer.Exit(code=1)


@template_app.command("edit")
def template_edit(
    template_id: str = typer.Argument(..., help="Template ID to edit"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="New comma-separated tags"),
    template_text: Optional[str] = typer.Option(None, "--text", help="New template text"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read template text from file"
    ),
):
    """Edit an existing template."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_templates_manager()

    template = manager.get_template(template_id)
    if not template:
        console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    try:
        # Read template text from file if provided
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            template_text = from_file.read_text(encoding="utf-8")

        # Parse tags
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]

        # Update template
        updated = manager.update_template(
            template_id=template_id,
            name=name,
            description=description,
            template_text=template_text,
            tags=tag_list,
        )

        if updated:
            info = f"""[bold]ID:[/bold] {updated.id}
[bold]Name:[/bold] {updated.name}
[bold]Description:[/bold] {updated.description}
[bold]Tags:[/bold] {', '.join(updated.tags) or 'None'}"""

            console.print(
                Panel(
                    info, title="[bold green]✓ Template Updated[/bold green]", border_style="green"
                )
            )
        else:
            console.print("[bold red]✗ Failed to update template[/bold red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]✗ Error updating template:[/bold red] {e}")
        raise typer.Exit(code=1)


@template_app.command("categories")
def template_categories():
    """List all template categories."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_templates_manager()

    categories = manager.get_categories()

    if not categories:
        console.print("[yellow]No categories found[/yellow]")
        return

    table = Table(title="Template Categories", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Templates", style="green")

    for category in categories:
        templates = manager.list_templates(category=category)
        table.add_row(category, str(len(templates)))

    console.print(table)


@template_app.command("stats")
def template_stats(
    template_id: Optional[str] = typer.Argument(None, help="Template ID for specific stats"),
):
    """Show template usage statistics."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    manager = get_templates_manager()

    if template_id:
        # Specific template stats
        template = manager.get_template(template_id)
        if not template:
            console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
            raise typer.Exit(code=1)

        stats = manager.get_stats(template_id)
        info = f"""[bold]Template:[/bold] {template.name}
[bold]ID:[/bold] {template_id}
[bold]Category:[/bold] {template.category}
[bold]Uses:[/bold] {stats['use_count']}
[bold]Last Used:[/bold] {stats.get('last_used', 'Never')}"""

        console.print(
            Panel(info, title="[bold cyan]Template Statistics[/bold cyan]", border_style="cyan")
        )
    else:
        # Overall stats
        stats = manager.get_stats()

        info = f"""[bold]Total Templates:[/bold] {stats['total_templates']}
[bold]Templates Used:[/bold] {stats['templates_used']}
[bold]Total Uses:[/bold] {stats['total_uses']}"""

        console.print(
            Panel(info, title="[bold cyan]Overall Statistics[/bold cyan]", border_style="cyan")
        )

        if stats["most_used"]:
            table = Table(title="Most Used Templates", show_header=True, header_style="bold yellow")
            table.add_column("Template ID", style="cyan")
            table.add_column("Uses", style="green")
            table.add_column("Last Used", style="magenta")

            for item in stats["most_used"]:
                template = manager.get_template(item["template_id"])
                name = (
                    f"{template.name} ({item['template_id']})" if template else item["template_id"]
                )
                last_used = item.get("last_used", "Never")
                if last_used != "Never":
                    last_used = last_used.split("T")[0]  # Show only date

                table.add_row(name, str(item["use_count"]), last_used)

            console.print("\n")
            console.print(table)


@template_app.command("export")
def template_export(
    template_id: str = typer.Argument(..., help="Template ID to export"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
):
    """Export a template to a YAML file."""
    from rich.console import Console

    console = Console()
    manager = get_templates_manager()

    template = manager.get_template(template_id)
    if not template:
        console.print(f"[bold red]✗ Template '{template_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    success = manager.export_template(template_id, output)
    if success:
        console.print(f"[green]✓ Template exported to:[/green] {output}")
    else:
        console.print("[bold red]✗ Failed to export template[/bold red]")
        raise typer.Exit(code=1)


@template_app.command("import")
def template_import(
    input_file: Path = typer.Argument(..., help="YAML file to import"),
):
    """Import a template from a YAML file."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_templates_manager()

    if not input_file.exists():
        console.print(f"[bold red]✗ File not found:[/bold red] {input_file}")
        raise typer.Exit(code=1)

    template = manager.import_template(input_file)
    if template:
        info = f"""[bold]ID:[/bold] {template.id}
[bold]Name:[/bold] {template.name}
[bold]Category:[/bold] {template.category}"""

        console.print(
            Panel(info, title="[bold green]✓ Template Imported[/bold green]", border_style="green")
        )
    else:
        console.print("[bold red]✗ Failed to import template[/bold red]")
        raise typer.Exit(code=1)


@template_app.command("validate")
def template_validate(
    template_id: str = typer.Argument(..., help="Template ID to validate"),
):
    """Validate a template for errors."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_templates_manager()

    validation = manager.validate_template(template_id)

    if validation.get("error"):
        console.print(f"[bold red]✗ {validation['error']}[/bold red]")
        raise typer.Exit(code=1)

    if validation["valid"]:
        info = f"""[bold green]✓ Template is valid[/bold green]

[bold]Placeholders:[/bold] {', '.join(validation['placeholders']) or 'None'}
[bold]Defined Variables:[/bold] {', '.join(validation['defined_variables']) or 'None'}
[bold]Required Variables:[/bold] {', '.join(validation['required_variables']) or 'None'}"""

        console.print(
            Panel(info, title="[bold green]Validation Success[/bold green]", border_style="green")
        )
    else:
        issues_text = "\n".join([f"• {issue}" for issue in validation["issues"]])
        info = f"""[bold red]✗ Template has issues:[/bold red]

{issues_text}

[bold]Placeholders:[/bold] {', '.join(validation['placeholders']) or 'None'}
[bold]Defined Variables:[/bold] {', '.join(validation['defined_variables']) or 'None'}"""

        console.print(
            Panel(info, title="[bold red]Validation Failed[/bold red]", border_style="red")
        )
        raise typer.Exit(code=1)


@template_app.command("preview")
def template_preview(
    template_id: str = typer.Argument(..., help="Template ID to preview"),
    vars: Optional[str] = typer.Option(
        None, "--vars", help="Variables as key=value pairs (comma-separated)"
    ),
):
    """Preview a template with optional variable values.

    Examples:
        promptc template preview my-template
        promptc template preview my-template --vars "name=John,age=25"
    """
    from app.template_preview import get_template_preview

    preview = get_template_preview()

    # Parse variables if provided
    variables = {}
    if vars:
        for pair in vars.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                variables[key.strip()] = value.strip()

    success, message = preview.preview_template(template_id, variables if variables else None)

    if not success:
        from rich.console import Console

        Console().print(f"[red]✗ {message}[/red]")
        raise typer.Exit(code=1)


@template_app.command("fill")
def template_fill(
    template_id: str = typer.Argument(..., help="Template ID to fill"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode for variable input"
    ),
    vars: Optional[str] = typer.Option(
        None, "--vars", help="Variables as key=value pairs (comma-separated)"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save to file"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy result to clipboard"),
):
    """Fill a template with variable values.

    Examples:
        promptc template fill my-template  # Interactive mode
        promptc template fill my-template --vars "name=John,age=25" --no-interactive
        promptc template fill my-template --output result.txt
    """
    from app.template_preview import get_template_preview
    from rich.console import Console

    preview = get_template_preview()
    console = Console()

    if interactive:
        # Interactive mode - prompt for each variable
        success, filled_content, variables_used = preview.interactive_fill(template_id)

        if not success:
            console.print(f"[red]✗ {filled_content}[/red]")
            raise typer.Exit(code=1)
    else:
        # Non-interactive mode - use provided variables
        from app.templates_manager import get_templates_manager

        manager = get_templates_manager()
        template = manager.get_template(template_id)

        if not template:
            console.print(f"[red]✗ Template '{template_id}' not found[/red]")
            raise typer.Exit(code=1)

        # Parse variables
        variables_used = {}
        if vars:
            for pair in vars.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    variables_used[key.strip()] = value.strip()

        # Validate variables
        is_valid, missing = preview.validate_variables(template.template_text, variables_used)
        if not is_valid:
            console.print(f"[red]✗ Missing variables: {', '.join(missing)}[/red]")
            raise typer.Exit(code=1)

        filled_content = preview.fill_template(template.template_text, variables_used)
        console.print("[green]✓ Template filled successfully[/green]")

    # Handle output
    if output:
        output.write_text(filled_content, encoding="utf-8")
        console.print(f"[green]✓ Saved to {output}[/green]")

    if copy:
        try:
            import pyperclip

            pyperclip.copy(filled_content)
            console.print("[green]✓ Copied to clipboard[/green]")
        except ImportError:
            console.print("[yellow]⚠ pyperclip not installed, skipping clipboard copy[/yellow]")


# ============================================================================
# Quick Snippets Commands
# ============================================================================


@snippets_app.command("add")
def snippets_add(
    snippet_id: str = typer.Argument(..., help="Unique snippet ID"),
    title: str = typer.Option(..., "--title", "-t", help="Snippet title"),
    content: str = typer.Option(None, "--content", "-c", help="Snippet content"),
    category: str = typer.Option(
        "general", "--category", help="Category (constraint, example, context, etc.)"
    ),
    description: str = typer.Option("", "--description", "-d", help="Optional description"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    language: str = typer.Option("en", "--language", "-l", help="Content language"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read content from file"
    ),
):
    """Add a new snippet."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    try:
        # Get content
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            content = from_file.read_text(encoding="utf-8")
        elif not content:
            console.print("[bold red]✗ Content is required[/bold red]")
            console.print("[dim]Use --content or --from-file[/dim]")
            raise typer.Exit(code=1)

        # Parse tags
        tag_list = [t.strip() for t in tags.split(",")] if tags else []

        # Add snippet
        snippet = manager.add(
            snippet_id=snippet_id,
            title=title,
            content=content,
            category=category,
            description=description,
            tags=tag_list,
            language=language,
        )

        content_preview = content[:100] + "..." if len(content) > 100 else content

        info = f"""[bold]ID:[/bold] {snippet.id}
[bold]Title:[/bold] {snippet.title}
[bold]Category:[/bold] {snippet.category}
[bold]Tags:[/bold] {', '.join(snippet.tags) or 'None'}
[bold]Language:[/bold] {snippet.language}

[bold]Content:[/bold]
{content_preview}"""

        console.print(
            Panel(info, title="[bold green]✓ Snippet Added[/bold green]", border_style="green")
        )

    except ValueError as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]✗ Error adding snippet:[/bold red] {e}")
        raise typer.Exit(code=1)


@snippets_app.command("list")
def snippets_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated)"
    ),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all snippets."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    snippets = manager.get_all(category=category, tags=tag_list, language=language)

    if not snippets:
        console.print("[yellow]No snippets found[/yellow]")
        return

    if json_output:
        output = [s.to_dict() for s in snippets]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    table = Table(title="Snippets", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Tags", style="blue", width=20)
    table.add_column("Uses", style="magenta", width=8)

    for snippet in snippets:
        tags_str = ", ".join(snippet.tags[:2])
        if len(snippet.tags) > 2:
            tags_str += "..."

        table.add_row(
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            tags_str,
            str(snippet.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(snippets)} snippets[/dim]")


@snippets_app.command("show")
def snippets_show(
    snippet_id: str = typer.Argument(..., help="Snippet ID to show"),
):
    """Show full snippet details."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    info = f"""[bold]ID:[/bold] {snippet.id}
[bold]Title:[/bold] {snippet.title}
[bold]Category:[/bold] {snippet.category}
[bold]Description:[/bold] {snippet.description or 'None'}
[bold]Tags:[/bold] {', '.join(snippet.tags) or 'None'}
[bold]Language:[/bold] {snippet.language}
[bold]Use Count:[/bold] {snippet.use_count}
[bold]Created:[/bold] {snippet.created_at.split('T')[0]}
[bold]Last Used:[/bold] {snippet.last_used.split('T')[0] if snippet.last_used else 'Never'}"""

    console.print(
        Panel(info, title="[bold cyan]Snippet Information[/bold cyan]", border_style="cyan")
    )

    console.print("\n[bold yellow]Content:[/bold yellow]")
    syntax = Syntax(snippet.content, "markdown", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, border_style="yellow"))


@snippets_app.command("use")
def snippets_use(
    snippet_id: str = typer.Argument(..., help="Snippet ID to use"),
    copy: bool = typer.Option(False, "--copy", help="Copy to clipboard"),
):
    """Use a snippet (shows content and increments use count)."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    content = manager.use(snippet_id)
    if content is None:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(content, title="[bold green]Snippet Content[/bold green]", border_style="green")
    )

    if copy:
        try:
            import pyperclip

            pyperclip.copy(content)
            console.print("\n[green]✓ Copied to clipboard[/green]")
        except ImportError:
            console.print("\n[yellow]⚠ pyperclip not installed - cannot copy to clipboard[/yellow]")


@snippets_app.command("delete")
def snippets_delete(
    snippet_id: str = typer.Argument(..., help="Snippet ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a snippet."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    if not force:
        confirm = Confirm.ask(f"Delete snippet '{snippet.title}' ({snippet_id})?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    success = manager.delete(snippet_id)
    if success:
        console.print(f"[green]✓ Snippet '{snippet_id}' deleted[/green]")
    else:
        console.print("[bold red]✗ Failed to delete snippet[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("edit")
def snippets_edit(
    snippet_id: str = typer.Argument(..., help="Snippet ID to edit"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="New title"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="New content"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    category: Optional[str] = typer.Option(None, "--category", help="New category"),
    tags: Optional[str] = typer.Option(None, "--tags", help="New comma-separated tags"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Read content from file"
    ),
):
    """Edit a snippet."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    manager = get_snippets_manager()

    snippet = manager.get(snippet_id)
    if not snippet:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)

    try:
        # Get content from file if provided
        if from_file:
            if not from_file.exists():
                console.print(f"[bold red]✗ File not found:[/bold red] {from_file}")
                raise typer.Exit(code=1)
            content = from_file.read_text(encoding="utf-8")

        # Parse tags
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]

        # Update snippet
        updated = manager.update(
            snippet_id=snippet_id,
            title=title,
            content=content,
            description=description,
            category=category,
            tags=tag_list,
        )

        if updated:
            info = f"""[bold]ID:[/bold] {updated.id}
[bold]Title:[/bold] {updated.title}
[bold]Category:[/bold] {updated.category}
[bold]Tags:[/bold] {', '.join(updated.tags) or 'None'}"""

            console.print(
                Panel(
                    info, title="[bold green]✓ Snippet Updated[/bold green]", border_style="green"
                )
            )
        else:
            console.print("[bold red]✗ Failed to update snippet[/bold red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]✗ Error updating snippet:[/bold red] {e}")
        raise typer.Exit(code=1)


@snippets_app.command("search")
def snippets_search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search snippets by query."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    results = manager.search(query)

    if not results:
        console.print(f"[yellow]No snippets found matching '{query}'[/yellow]")
        return

    if json_output:
        output = [s.to_dict() for s in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    table = Table(title=f"Search Results for '{query}'", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Uses", style="magenta", width=8)

    for snippet in results:
        table.add_row(
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            str(snippet.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Found: {len(results)} snippets[/dim]")


@snippets_app.command("categories")
def snippets_categories():
    """List all snippet categories."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    categories = manager.get_categories()

    if not categories:
        console.print("[yellow]No categories found[/yellow]")
        return

    table = Table(title="Snippet Categories", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Snippets", style="green")

    for category in categories:
        snippets = manager.get_all(category=category)
        table.add_row(category, str(len(snippets)))

    console.print(table)


@snippets_app.command("tag")
def snippets_tag(
    snippet_id: str = typer.Argument(..., help="Snippet ID"),
    tag: str = typer.Argument(..., help="Tag to add"),
):
    """Add a tag to a snippet."""
    from rich.console import Console

    console = Console()
    manager = get_snippets_manager()

    success = manager.add_tag(snippet_id, tag)
    if success:
        console.print(f"[green]✓ Tag '{tag}' added to snippet '{snippet_id}'[/green]")
    else:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("untag")
def snippets_untag(
    snippet_id: str = typer.Argument(..., help="Snippet ID"),
    tag: str = typer.Argument(..., help="Tag to remove"),
):
    """Remove a tag from a snippet."""
    from rich.console import Console

    console = Console()
    manager = get_snippets_manager()

    success = manager.remove_tag(snippet_id, tag)
    if success:
        console.print(f"[green]✓ Tag '{tag}' removed from snippet '{snippet_id}'[/green]")
    else:
        console.print(f"[bold red]✗ Snippet '{snippet_id}' not found or tag not present[/bold red]")
        raise typer.Exit(code=1)


@snippets_app.command("stats")
def snippets_stats():
    """Show snippet statistics."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    stats = manager.get_stats()

    info = f"""[bold]Total Snippets:[/bold] {stats['total_snippets']}
[bold]Total Uses:[/bold] {stats['total_uses']}"""

    console.print(
        Panel(info, title="[bold cyan]Snippet Statistics[/bold cyan]", border_style="cyan")
    )

    # Categories
    if stats["categories"]:
        console.print("\n[bold yellow]By Category:[/bold yellow]")
        for category, count in sorted(stats["categories"].items()):
            console.print(f"  [cyan]{category}:[/cyan] {count}")

    # Languages
    if stats["languages"]:
        console.print("\n[bold yellow]By Language:[/bold yellow]")
        for language, count in sorted(stats["languages"].items()):
            console.print(f"  [cyan]{language}:[/cyan] {count}")

    # Most used
    if stats["most_used"]:
        table = Table(title="Most Used Snippets", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Uses", style="magenta")

        for item in stats["most_used"]:
            table.add_row(
                item["id"],
                item["title"],
                item["category"],
                str(item["use_count"]),
            )

        console.print("\n")
        console.print(table)


@snippets_app.command("most-used")
def snippets_most_used(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of snippets to show"),
):
    """Show most used snippets."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_snippets_manager()

    most_used = manager.get_most_used(limit=limit)

    if not most_used:
        console.print("[yellow]No snippets found[/yellow]")
        return

    table = Table(
        title=f"Top {limit} Most Used Snippets", show_header=True, header_style="bold cyan"
    )
    table.add_column("Rank", style="magenta", width=6)
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Title", style="green", width=30)
    table.add_column("Category", style="yellow", width=15)
    table.add_column("Uses", style="magenta", width=8)

    for rank, snippet in enumerate(most_used, 1):
        table.add_row(
            str(rank),
            snippet.id,
            snippet.title[:28] + "..." if len(snippet.title) > 28 else snippet.title,
            snippet.category,
            str(snippet.use_count),
        )

    console.print(table)


@snippets_app.command("clear")
def snippets_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all snippets."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()

    if not force:
        confirm = Confirm.ask("Clear ALL snippets? This cannot be undone!")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    manager = get_snippets_manager()
    manager.clear()

    console.print("[green]✓ All snippets cleared[/green]")


# ============================================================================
# Favorites/Bookmarks Commands
# ============================================================================


@favorites_app.command("add")
def favorites_add(
    prompt_id: str = typer.Argument(..., help="Prompt ID from history"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Notes about this favorite"),
):
    """
    Add a prompt to favorites from history

    Example:
        promptc favorites add abc123 --tags "python,tutorial" --notes "Great example"
    """
    from rich.console import Console

    console = Console()

    # Get prompt from history
    history_mgr = get_history_manager()
    history_entry = history_mgr.get_by_id(prompt_id)

    if not history_entry:
        console.print(f"[yellow]Prompt ID '{prompt_id}' not found in history[/yellow]")
        raise typer.Exit(code=1)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    # Add to favorites
    favorites_mgr = get_favorites_manager()
    entry = favorites_mgr.add(
        prompt_id=history_entry.id,
        prompt_text=history_entry.prompt_text,
        domain=history_entry.domain,
        language=history_entry.language,
        score=history_entry.score,
        tags=tag_list,
        notes=notes or "",
    )

    console.print(
        f"[green]✓ Added to favorites:[/green] {entry.id}\n"
        f"  Prompt: {entry.prompt_text[:50]}...\n"
        f"  Tags: {', '.join(entry.tags) if entry.tags else 'none'}"
    )


@favorites_app.command("list")
def favorites_list(
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated)"
    ),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    List all favorite prompts

    Example:
        promptc favorites list
        promptc favorites list --tags python
        promptc favorites list --domain education
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Get favorites
    favorites = favorites_mgr.get_all(tags=tag_list, domain=domain)

    if json_output:
        import json

        output = [f.to_dict() for f in favorites]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not favorites:
        console.print("[yellow]No favorites found[/yellow]")
        return

    console.print(f"\n[bold cyan]Favorites[/bold cyan] [dim]({len(favorites)} total)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Tags", width=20)
    table.add_column("Uses", justify="right", width=6)
    table.add_column("Prompt", width=40)

    for fav in favorites:
        tags_str = ", ".join(fav.tags[:3]) if fav.tags else "-"
        if len(fav.tags) > 3:
            tags_str += "..."

        table.add_row(
            fav.id,
            f"{fav.score:.1f}",
            fav.domain,
            tags_str,
            str(fav.use_count),
            fav.prompt_text[:37] + "..." if len(fav.prompt_text) > 40 else fav.prompt_text,
        )

    console.print(table)


@favorites_app.command("show")
def favorites_show(favorite_id: str = typer.Argument(..., help="Favorite ID")):
    """
    Show full details of a favorite

    Example:
        promptc favorites show abc123
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    entry = favorites_mgr.get_by_id(favorite_id)

    if not entry:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)

    info = f"""[bold]ID:[/bold] {entry.id}
[bold]Prompt ID:[/bold] {entry.prompt_id}
[bold]Domain:[/bold] {entry.domain}
[bold]Language:[/bold] {entry.language.upper()}
[bold]Score:[/bold] {entry.score:.1f}
[bold]Use Count:[/bold] {entry.use_count}
[bold]Tags:[/bold] {', '.join(entry.tags) if entry.tags else 'none'}
[bold]Added:[/bold] {entry.timestamp}

[bold]Prompt:[/bold]
{entry.prompt_text}

[bold]Notes:[/bold]
{entry.notes if entry.notes else '(no notes)'}"""

    console.print(
        Panel(info, title=f"[bold cyan]Favorite: {entry.id}[/bold cyan]", border_style="cyan")
    )


@favorites_app.command("remove")
def favorites_remove(favorite_id: str = typer.Argument(..., help="Favorite ID to remove")):
    """
    Remove a favorite

    Example:
        promptc favorites remove abc123
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.remove(favorite_id):
        console.print(f"[green]✓ Removed favorite: {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("search")
def favorites_search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Search favorites by text

    Example:
        promptc favorites search "python tutorial"
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    results = favorites_mgr.search(query)

    if json_output:
        import json

        output = [f.to_dict() for f in results]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not results:
        console.print(f"[yellow]No favorites found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold cyan]Search Results[/bold cyan] [dim]({len(results)} matches)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Prompt", width=50)

    for fav in results:
        # Highlight query in text
        prompt_display = (
            fav.prompt_text[:47] + "..." if len(fav.prompt_text) > 50 else fav.prompt_text
        )
        table.add_row(fav.id, f"{fav.score:.1f}", fav.domain, prompt_display)

    console.print(table)


@favorites_app.command("tag")
def favorites_tag(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    tag: str = typer.Argument(..., help="Tag to add"),
):
    """
    Add a tag to a favorite

    Example:
        promptc favorites tag abc123 important
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.add_tag(favorite_id, tag):
        console.print(f"[green]✓ Added tag '{tag}' to favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("untag")
def favorites_untag(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    tag: str = typer.Argument(..., help="Tag to remove"),
):
    """
    Remove a tag from a favorite

    Example:
        promptc favorites untag abc123 important
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.remove_tag(favorite_id, tag):
        console.print(f"[green]✓ Removed tag '{tag}' from favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("note")
def favorites_note(
    favorite_id: str = typer.Argument(..., help="Favorite ID"),
    notes: str = typer.Argument(..., help="Notes text"),
):
    """
    Update notes for a favorite

    Example:
        promptc favorites note abc123 "This is my best prompt for tutorials"
    """
    from rich.console import Console

    console = Console()
    favorites_mgr = get_favorites_manager()

    if favorites_mgr.update_notes(favorite_id, notes):
        console.print(f"[green]✓ Updated notes for favorite {favorite_id}[/green]")
    else:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)


@favorites_app.command("stats")
def favorites_stats():
    """
    Show favorites statistics

    Example:
        promptc favorites stats
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    stats = favorites_mgr.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]No favorites yet[/yellow]")
        return

    info = f"""[bold]Total Favorites:[/bold] {stats['total']}
[bold]Total Uses:[/bold] {stats['total_uses']}
[bold]Avg Score:[/bold] {stats['avg_score']:.1f}

[bold]Top Domains:[/bold]"""

    for domain, count in list(stats["domains"].items())[:5]:
        info += f"\n  {domain}: {count}"

    if stats["tags"]:
        info += "\n\n[bold]Top Tags:[/bold]"
        for tag, count in list(stats["tags"].items())[:10]:
            info += f"\n  {tag}: {count}"

    info += "\n\n[bold]Languages:[/bold]"
    for lang, count in stats["languages"].items():
        info += f"\n  {lang.upper()}: {count}"

    console.print(
        Panel(info, title="[bold cyan]Favorites Statistics[/bold cyan]", border_style="cyan")
    )


@favorites_app.command("most-used")
def favorites_most_used(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of favorites to show"),
):
    """
    Show most frequently used favorites

    Example:
        promptc favorites most-used --limit 5
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    favorites_mgr = get_favorites_manager()

    favorites = favorites_mgr.get_most_used(limit=limit)

    if not favorites:
        console.print("[yellow]No favorites found[/yellow]")
        return

    console.print(
        f"\n[bold cyan]Most Used Favorites[/bold cyan] [dim](Top {len(favorites)})[/dim]\n"
    )

    table = Table(show_header=True)
    table.add_column("Rank", justify="right", width=6)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Uses", justify="right", width=6)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Domain", width=12)
    table.add_column("Prompt", width=40)

    for i, fav in enumerate(favorites, 1):
        table.add_row(
            str(i),
            fav.id,
            str(fav.use_count),
            f"{fav.score:.1f}",
            fav.domain,
            fav.prompt_text[:37] + "..." if len(fav.prompt_text) > 40 else fav.prompt_text,
        )

    console.print(table)


@favorites_app.command("use")
def favorites_use(favorite_id: str = typer.Argument(..., help="Favorite ID to use")):
    """
    Use a favorite (increments use count and shows the prompt)

    Example:
        promptc favorites use abc123
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    favorites_mgr = get_favorites_manager()

    entry = favorites_mgr.get_by_id(favorite_id)

    if not entry:
        console.print(f"[yellow]Favorite '{favorite_id}' not found[/yellow]")
        raise typer.Exit(code=1)

    # Increment use count
    favorites_mgr.increment_use_count(favorite_id)

    # Show the prompt
    info = f"""[bold]{entry.prompt_text}[/bold]

[dim]Domain: {entry.domain} | Score: {entry.score:.1f} | Uses: {entry.use_count + 1}[/dim]"""

    console.print(
        Panel(info, title=f"[bold cyan]Favorite: {entry.id}[/bold cyan]", border_style="cyan")
    )

    # Copy to clipboard if possible
    try:
        import pyperclip

        pyperclip.copy(entry.prompt_text)
        console.print("\n[green]✓ Copied to clipboard[/green]")
    except ImportError:
        console.print(
            "\n[dim]Tip: Install pyperclip for clipboard support (pip install pyperclip)[/dim]"
        )


@favorites_app.command("clear")
def favorites_clear(force: bool = typer.Option(False, "--force", help="Skip confirmation")):
    """
    Clear all favorites

    Example:
        promptc favorites clear --force
    """
    from rich.console import Console

    console = Console()

    if not force:
        confirm = typer.confirm("Clear all favorites?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    favorites_mgr = get_favorites_manager()
    favorites_mgr.clear()

    console.print("[green]✓ All favorites cleared[/green]")


# ============================================================
# COLLECTIONS/WORKSPACES COMMANDS
# ============================================================


@collections_app.command("create")
def collections_create(
    collection_id: str = typer.Argument(..., help="Unique collection ID"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    tags: List[str] = typer.Option(
        None, "--tag", "-t", help="Tags (can be specified multiple times)"
    ),
    color: str = typer.Option("blue", "--color", "-c", help="Color for UI display"),
    set_active: bool = typer.Option(False, "--active", "-a", help="Set as active collection"),
):
    """Create a new collection/workspace."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.create(
            collection_id=collection_id,
            name=name,
            description=description,
            tags=tags or [],
            color=color,
        )

        if set_active:
            collections_mgr.set_active_collection(collection_id)

        console.print(
            Panel(
                f"[bold green]Collection Created[/bold green]\n\n"
                f"[cyan]ID:[/cyan] {collection.id}\n"
                f"[cyan]Name:[/cyan] {collection.name}\n"
                f"[cyan]Description:[/cyan] {collection.description or '(none)'}\n"
                f"[cyan]Tags:[/cyan] {', '.join(collection.tags) if collection.tags else '(none)'}\n"
                f"[cyan]Color:[/cyan] {collection.color}\n"
                f"[cyan]Active:[/cyan] {'Yes' if set_active else 'No'}",
                title="✓ Success",
                border_style="green",
            )
        )

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("list")
def collections_list(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    archived: Optional[bool] = typer.Option(
        None, "--archived", "-a", help="Filter by archived status"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all collections."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    collections_mgr = get_collections_manager()

    collections = collections_mgr.get_all(tag=tag, archived=archived)

    if json_output:
        data = [c.to_dict() for c in collections]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not collections:
        console.print("[yellow]No collections found[/yellow]")
        return

    active_id = collections_mgr.get_active_collection()

    table = Table(title="Collections", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Items", justify="right")
    table.add_column("Tags")
    table.add_column("Status")
    table.add_column("Used", justify="right")

    for collection in collections:
        total_items = len(collection.prompts) + len(collection.templates) + len(collection.snippets)

        status_parts = []
        if collection.id == active_id:
            status_parts.append("[bold green]●Active[/bold green]")
        if collection.is_archived:
            status_parts.append("[dim]Archived[/dim]")

        status = " ".join(status_parts) if status_parts else ""

        table.add_row(
            collection.id,
            collection.name,
            str(total_items),
            ", ".join(collection.tags) if collection.tags else "",
            status,
            str(collection.use_count),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(collections)} collections[/dim]")


@collections_app.command("show")
def collections_show(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details of a collection."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    collections_mgr = get_collections_manager()

    collection = collections_mgr.get(collection_id)
    if not collection:
        console.print(f"[red]Collection '{collection_id}' not found[/red]")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(collection.to_dict(), indent=2, ensure_ascii=False))
        return

    active_id = collections_mgr.get_active_collection()
    is_active = collection.id == active_id

    # Overview panel
    overview = (
        f"[cyan]Name:[/cyan] {collection.name}\n"
        f"[cyan]ID:[/cyan] {collection.id}\n"
        f"[cyan]Description:[/cyan] {collection.description or '(none)'}\n"
        f"[cyan]Tags:[/cyan] {', '.join(collection.tags) if collection.tags else '(none)'}\n"
        f"[cyan]Color:[/cyan] {collection.color}\n"
        f"[cyan]Created:[/cyan] {collection.created_at}\n"
        f"[cyan]Updated:[/cyan] {collection.updated_at}\n"
        f"[cyan]Use Count:[/cyan] {collection.use_count}\n"
        f"[cyan]Active:[/cyan] {'[bold green]Yes[/bold green]' if is_active else 'No'}\n"
        f"[cyan]Archived:[/cyan] {'Yes' if collection.is_archived else 'No'}"
    )

    console.print(Panel(overview, title=f"Collection: {collection.name}", border_style="cyan"))

    # Items table
    table = Table(title="Items", show_header=True, header_style="bold cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Count", justify="right", style="green")
    table.add_column("IDs", style="dim")

    table.add_row(
        "Prompts",
        str(len(collection.prompts)),
        ", ".join(collection.prompts[:3]) + ("..." if len(collection.prompts) > 3 else ""),
    )
    table.add_row(
        "Templates",
        str(len(collection.templates)),
        ", ".join(collection.templates[:3]) + ("..." if len(collection.templates) > 3 else ""),
    )
    table.add_row(
        "Snippets",
        str(len(collection.snippets)),
        ", ".join(collection.snippets[:3]) + ("..." if len(collection.snippets) > 3 else ""),
    )

    console.print(table)


@collections_app.command("switch")
def collections_switch(
    collection_id: Optional[str] = typer.Argument(
        None, help="Collection ID (omit to clear active)"
    ),
):
    """Switch to a collection (set as active)."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        if collection_id is None:
            collections_mgr.set_active_collection(None)
            console.print("[green]✓ Active collection cleared[/green]")
        else:
            collections_mgr.set_active_collection(collection_id)
            collection = collections_mgr.get(collection_id)
            console.print(
                f"[green]✓ Switched to collection:[/green] [cyan]{collection.name}[/cyan] ({collection_id})"
            )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-prompt")
def collections_add_prompt(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    prompt_id: str = typer.Argument(..., help="Prompt ID/hash to add"),
):
    """Add a prompt to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_prompt(collection_id, prompt_id)
        console.print(
            f"[green]✓ Added prompt[/green] [yellow]{prompt_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-template")
def collections_add_template(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    template_id: str = typer.Argument(..., help="Template ID to add"),
):
    """Add a template to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_template(collection_id, template_id)
        console.print(
            f"[green]✓ Added template[/green] [yellow]{template_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("add-snippet")
def collections_add_snippet(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    snippet_id: str = typer.Argument(..., help="Snippet ID to add"),
):
    """Add a snippet to a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.add_snippet(collection_id, snippet_id)
        console.print(
            f"[green]✓ Added snippet[/green] [yellow]{snippet_id}[/yellow] "
            f"[green]to[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-prompt")
def collections_remove_prompt(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    prompt_id: str = typer.Argument(..., help="Prompt ID to remove"),
):
    """Remove a prompt from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_prompt(collection_id, prompt_id)
        console.print(
            f"[green]✓ Removed prompt[/green] [yellow]{prompt_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-template")
def collections_remove_template(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    template_id: str = typer.Argument(..., help="Template ID to remove"),
):
    """Remove a template from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_template(collection_id, template_id)
        console.print(
            f"[green]✓ Removed template[/green] [yellow]{template_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("remove-snippet")
def collections_remove_snippet(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    snippet_id: str = typer.Argument(..., help="Snippet ID to remove"),
):
    """Remove a snippet from a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.remove_snippet(collection_id, snippet_id)
        console.print(
            f"[green]✓ Removed snippet[/green] [yellow]{snippet_id}[/yellow] "
            f"[green]from[/green] [cyan]{collection.name}[/cyan]"
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("update")
def collections_update(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", "-t", help="New tags (replaces existing)"
    ),
    color: Optional[str] = typer.Option(None, "--color", "-c", help="New color"),
):
    """Update a collection's metadata."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.update(
            collection_id=collection_id,
            name=name,
            description=description,
            tags=tags,
            color=color,
        )
        console.print(f"[green]✓ Updated collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("delete")
def collections_delete(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    collection = collections_mgr.get(collection_id)
    if not collection:
        console.print(f"[red]Collection '{collection_id}' not found[/red]")
        raise typer.Exit(code=1)

    if not force:
        console.print(f"[yellow]Delete collection '{collection.name}' ({collection_id})?[/yellow]")
        confirm = typer.confirm("This cannot be undone.")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    collections_mgr.delete(collection_id)
    console.print(f"[green]✓ Deleted collection:[/green] {collection.name}")


@collections_app.command("archive")
def collections_archive(
    collection_id: str = typer.Argument(..., help="Collection ID"),
):
    """Archive a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.archive(collection_id)
        console.print(f"[green]✓ Archived collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("unarchive")
def collections_unarchive(
    collection_id: str = typer.Argument(..., help="Collection ID"),
):
    """Unarchive a collection."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        collection = collections_mgr.unarchive(collection_id)
        console.print(f"[green]✓ Unarchived collection:[/green] [cyan]{collection.name}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("stats")
def collections_stats():
    """Show collection statistics."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    collections_mgr = get_collections_manager()

    stats = collections_mgr.get_stats()

    # Overview panel
    overview = (
        f"[cyan]Total Collections:[/cyan] {stats['total_collections']}\n"
        f"[cyan]Active Collections:[/cyan] {stats['active_collections']}\n"
        f"[cyan]Archived Collections:[/cyan] {stats['archived_collections']}\n\n"
        f"[cyan]Total Prompts:[/cyan] {stats['total_prompts']}\n"
        f"[cyan]Total Templates:[/cyan] {stats['total_templates']}\n"
        f"[cyan]Total Snippets:[/cyan] {stats['total_snippets']}\n\n"
        f"[cyan]Active Collection:[/cyan] {stats['active_collection'] or '(none)'}"
    )

    console.print(Panel(overview, title="Collection Statistics", border_style="cyan"))

    # Most used table
    if stats["most_used"]:
        table = Table(title="Most Used Collections", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Uses", justify="right", style="yellow")
        table.add_column("Items", justify="right", style="magenta")

        for item in stats["most_used"]:
            table.add_row(item["id"], item["name"], str(item["use_count"]), str(item["items"]))

        console.print(table)


@collections_app.command("export")
def collections_export(
    collection_id: str = typer.Argument(..., help="Collection ID"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
):
    """Export a collection to JSON."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    try:
        data = collections_mgr.export_collection(collection_id)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓ Exported to:[/green] {output}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("import")
def collections_import(
    input_file: Path = typer.Argument(..., help="Input JSON file"),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-o", help="Overwrite if collection exists"
    ),
):
    """Import a collection from JSON."""
    from rich.console import Console

    console = Console()
    collections_mgr = get_collections_manager()

    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        raise typer.Exit(code=1)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        collection = collections_mgr.import_collection(data, overwrite=overwrite)
        console.print(
            f"[green]✓ Imported collection:[/green] [cyan]{collection.name}[/cyan] ({collection.id})"
        )

    except (ValueError, json.JSONDecodeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@collections_app.command("clear")
def collections_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all collections."""
    from rich.console import Console

    console = Console()

    if not force:
        confirm = typer.confirm("Clear all collections?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit()

    collections_mgr = get_collections_manager()
    collections_mgr.clear()

    console.print("[green]✓ All collections cleared[/green]")


# ============================================================
# SMART SEARCH COMMAND
# ============================================================


@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Search query"),
    result_type: Optional[List[str]] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type: history, favorite, template, snippet, collection",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
    min_score: float = typer.Option(
        0.0, "--min-score", "-s", help="Minimum relevance score (0-100)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    show_stats: bool = typer.Option(False, "--stats", help="Show search statistics before results"),
    export: Optional[str] = typer.Option(
        None, "--export", "-e", help="Export results to file (CSV or JSON based on extension)"
    ),
):
    """Search across all PromptC data (history, favorites, templates, snippets, collections)."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from app.search_history import get_search_history_manager
    from datetime import datetime
    from pathlib import Path
    import json
    import csv

    console = Console()
    search_engine = get_search_engine()
    history_mgr = get_search_history_manager()

    # Show stats if requested
    if show_stats:
        stats = search_engine.get_stats()
        stats_text = (
            f"[cyan]Searchable Items:[/cyan]\n"
            f"  • History: {stats['history']}\n"
            f"  • Favorites: {stats['favorites']}\n"
            f"  • Templates: {stats['templates']}\n"
            f"  • Snippets: {stats['snippets']}\n"
            f"  • Collections: {stats['collections']}\n"
            f"  [bold]Total: {sum(stats.values())}[/bold]"
        )
        console.print(Panel(stats_text, title="Search Index", border_style="cyan"))
        console.print()

    # Parse result types
    types_filter = None
    if result_type:
        try:
            types_filter = [SearchResultType(t.lower()) for t in result_type]
        except ValueError:
            console.print(
                "[red]Invalid type. Valid types: history, favorite, template, snippet, collection[/red]"
            )
            raise typer.Exit(code=1)

    # Perform search
    results = search_engine.search(
        query=query, result_types=types_filter, limit=limit, min_score=min_score
    )

    # JSON output
    if json_output:
        output_data = {
            "query": query,
            "total_results": len(results),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        return

    # No results
    if not results:
        console.print(f"[yellow]No results found for:[/yellow] [bold]{query}[/bold]")
        console.print("[dim]Try a different query or lower --min-score[/dim]")
        return

    # Display results in a table
    table = Table(
        title=f"Search Results for '{query}' ({len(results)} found)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Score", justify="right", style="green", width=6)
    table.add_column("Title", style="cyan")
    table.add_column("Preview", style="dim")

    for result in results:
        # Type icon
        type_icons = {
            "history": "📝",
            "favorite": "⭐",
            "template": "📄",
            "snippet": "📋",
            "collection": "🗂️",
        }
        type_str = f"{type_icons.get(result.result_type.value, '•')} {result.result_type.value}"

        # Score
        score_str = f"{result.score:.1f}"

        # Title (truncate if too long)
        title = result.title[:50] + ("..." if len(result.title) > 50 else "")

        # Preview (truncate content)
        preview = result.content[:80] + ("..." if len(result.content) > 80 else "")
        preview = preview.replace("\n", " ")

        table.add_row(type_str, score_str, title, preview)

    console.print(table)

    # Export results if requested
    if export:
        try:
            export_path = Path(export)
            if export_path.suffix.lower() == ".csv":
                # Export as CSV
                with open(export_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Type", "Score", "Title", "Content", "ID"])
                    for result in results:
                        writer.writerow(
                            [
                                result.result_type.value,
                                f"{result.score:.2f}",
                                result.title,
                                result.content,
                                result.id,
                            ]
                        )
                console.print(
                    f"\n✅ [green]Exported {len(results)} results to {export_path}[/green]"
                )
            else:
                # Export as JSON (default)
                export_data = {
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "result_count": len(results),
                    "filters": {
                        "types": result_type,
                        "min_score": min_score,
                        "limit": limit,
                    },
                    "results": [
                        {
                            "type": r.result_type.value,
                            "score": r.score,
                            "id": r.id,
                            "title": r.title,
                            "content": r.content,
                            "metadata": r.metadata,
                        }
                        for r in results
                    ],
                }
                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                console.print(
                    f"\n✅ [green]Exported {len(results)} results to {export_path}[/green]"
                )
        except Exception as e:
            console.print(f"\n❌ [red]Export failed: {e}[/red]")

    # Add to search history
    history_mgr.add(
        query=query, result_count=len(results), types_filter=result_type, min_score=min_score
    )

    # Show footer with useful info
    console.print("\n[dim]💡 Tip: Use --type to filter results, --min-score to set threshold[/dim]")
    console.print(
        "[dim]   Use --export results.json to save results, 'promptc search-history' to see recent searches[/dim]"
    )


@app.command("search-history")
def search_history_command(
    clear: bool = typer.Option(False, "--clear", help="Clear search history"),
    rerun: Optional[int] = typer.Option(None, "--rerun", "-r", help="Rerun search by index (0-9)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View and manage recent search queries."""
    from rich.console import Console
    from rich.table import Table
    from app.search_history import get_search_history_manager
    from datetime import datetime
    import json

    console = Console()
    history_mgr = get_search_history_manager()

    # Clear history if requested
    if clear:
        history_mgr.clear()
        console.print("✅ [green]Search history cleared[/green]")
        return

    # Rerun a search if requested
    if rerun is not None:
        entry = history_mgr.get_by_index(rerun)
        if entry is None:
            console.print(f"❌ [red]Invalid index: {rerun}[/red]")
            raise typer.Exit(code=1)

        console.print(f"🔄 [cyan]Rerunning search: '{entry.query}'[/cyan]\n")

        # Build command arguments

        args = ["search", entry.query]
        if entry.types_filter:
            for t in entry.types_filter:
                args.extend(["--type", t])
        if entry.min_score > 0:
            args.extend(["--min-score", str(entry.min_score)])

        # Rerun the search
        search_command(
            query=entry.query,
            result_type=entry.types_filter,
            limit=20,
            min_score=entry.min_score,
            json_output=False,
            show_stats=False,
            export=None,
        )
        return

    # Show history
    recent = history_mgr.get_recent()

    if not recent:
        console.print("[yellow]No search history yet[/yellow]")
        console.print("\n[dim]💡 Tip: Your searches will be automatically tracked here[/dim]")
        return

    if json_output:
        output = [
            {
                "index": i,
                "query": entry.query,
                "result_count": entry.result_count,
                "timestamp": entry.timestamp,
                "types_filter": entry.types_filter,
                "min_score": entry.min_score,
            }
            for i, entry in enumerate(recent)
        ]
        console.print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Display as table
    table = Table(
        title="Recent Searches (Last 10)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="yellow", width=3)
    table.add_column("Query", style="cyan", width=30)
    table.add_column("Results", justify="right", style="green", width=8)
    table.add_column("Filters", style="dim", width=20)
    table.add_column("When", style="magenta", width=20)

    for i, entry in enumerate(recent):
        # Parse timestamp
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            when = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            when = entry.timestamp[:16]

        # Format filters
        filters = []
        if entry.types_filter:
            filters.append(f"types: {','.join(entry.types_filter)}")
        if entry.min_score > 0:
            filters.append(f"score≥{entry.min_score}")
        filter_str = "; ".join(filters) if filters else "-"

        # Truncate query if too long
        query_display = entry.query[:28] + ("..." if len(entry.query) > 28 else "")

        table.add_row(str(i), query_display, str(entry.result_count), filter_str, when)

    console.print(table)
    console.print(
        "\n[dim]💡 Tip: Use --rerun N to repeat a search (e.g., 'promptc search-history --rerun 0')[/dim]"
    )
    console.print("[dim]   Use --clear to delete all search history[/dim]")


@app.command("tui")
def tui_command():
    """Launch the Terminal UI (TUI) for interactive searching and browsing."""
    from rich.console import Console

    try:
        from app.tui import run_tui

        run_tui()
    except ImportError:
        console = Console()
        console.print("[red]❌ Error: 'textual' library not installed[/red]")
        console.print("\n[yellow]To use the TUI, install textual:[/yellow]")
        console.print("  [cyan]pip install textual[/cyan]")
        console.print("\n[dim]Or install all requirements:[/dim]")
        console.print("  [cyan]pip install -r requirements.txt[/cyan]")
        raise typer.Exit(code=1)
    except Exception as e:
        console = Console()
        console.print(f"[red]❌ Error launching TUI: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("last")
def last_command(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show the last search query and re-run it."""
    from rich.console import Console
    from rich.panel import Panel
    from app.quick_actions import get_quick_actions
    import json

    console = Console()
    qa = get_quick_actions()

    last_search = qa.get_last_search()

    if not last_search:
        console.print("[yellow]No search history found[/yellow]")
        console.print("\n[dim]💡 Tip: Use 'promptc search' to perform searches[/dim]")
        raise typer.Exit(code=0)

    if json_output:
        console.print(json.dumps(last_search, indent=2, ensure_ascii=False))
        return

    # Display last search info
    query = last_search["query"]
    result_count = last_search["result_count"]
    timestamp = last_search["timestamp"][:19].replace("T", " ")
    types_filter = last_search.get("types_filter") or []
    min_score = last_search.get("min_score", 0.0)

    info_text = f"[bold cyan]Query:[/bold cyan] {query}\n"
    info_text += f"[bold green]Results:[/bold green] {result_count}\n"
    info_text += f"[bold yellow]When:[/bold yellow] {timestamp}\n"
    if types_filter:
        info_text += f"[bold magenta]Filters:[/bold magenta] {', '.join(types_filter)}\n"
    if min_score > 0:
        info_text += f"[bold blue]Min Score:[/bold blue] {min_score}"

    panel = Panel(
        info_text,
        title="[bold white]Last Search[/bold white]",
        border_style="cyan",
    )
    console.print(panel)

    # Ask to re-run
    console.print("\n[dim]Re-running search...[/dim]\n")

    # Re-run the search
    search_command(
        query=query,
        result_type=types_filter if types_filter else None,
        limit=20,
        min_score=min_score,
        json_output=False,
        show_stats=False,
        export=None,
    )


@app.command("top")
def top_command(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of top favorites to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show top favorites sorted by score."""
    from rich.console import Console
    from rich.table import Table
    from app.quick_actions import get_quick_actions
    import json

    console = Console()
    qa = get_quick_actions()

    top_favs = qa.get_top_favorites(limit=limit)

    if not top_favs:
        console.print("[yellow]No favorites found[/yellow]")
        console.print("\n[dim]💡 Tip: Use 'promptc favorites add' to save your best prompts[/dim]")
        raise typer.Exit(code=0)

    if json_output:
        console.print(json.dumps(top_favs, indent=2, ensure_ascii=False))
        return

    # Display as table
    table = Table(
        title=f"[bold cyan]Top {len(top_favs)} Favorites[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("#", style="yellow", width=3)
    table.add_column("Score", style="green", width=6)
    table.add_column("Domain", style="cyan", width=12)
    table.add_column("Prompt", style="white", width=50)
    table.add_column("Uses", style="blue", width=5)

    for i, fav in enumerate(top_favs, 1):
        score_str = f"{fav['score']:.1f}" if fav["score"] else "N/A"
        domain_str = fav["domain"] or "general"
        prompt_preview = fav["prompt_text"][:50]
        if len(fav["prompt_text"]) > 50:
            prompt_preview += "..."
        uses = str(fav["use_count"])

        table.add_row(str(i), score_str, domain_str, prompt_preview, uses)

    console.print(table)
    console.print(f"\n[dim]💡 Showing top {len(top_favs)} of all favorites sorted by score[/dim]")


@app.command("random")
def random_command(
    item_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Item type: 'template' or 'snippet'"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Get a random template or snippet for inspiration."""
    from rich.console import Console
    from rich.panel import Panel
    from app.quick_actions import get_quick_actions
    import json

    console = Console()
    qa = get_quick_actions()

    # Validate type if provided
    if item_type and item_type not in ["template", "snippet"]:
        console.print(f"[red]❌ Invalid type: {item_type}[/red]")
        console.print("[yellow]Valid types: 'template', 'snippet'[/yellow]")
        raise typer.Exit(code=1)

    result = qa.get_random_item(item_type=item_type)

    if not result:
        console.print("[yellow]No items found[/yellow]")
        if item_type:
            console.print(f"\n[dim]💡 Tip: Add {item_type}s using 'promptc {item_type}s add'[/dim]")
        else:
            console.print(
                "\n[dim]💡 Tip: Add templates or snippets to get random suggestions[/dim]"
            )
        raise typer.Exit(code=0)

    result_type = result["type"]
    data = result["data"]

    if json_output:
        console.print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Display based on type
    if result_type == "template":
        name = data["name"]
        description = data.get("description", "No description")
        template_text = data["template_text"]
        variables = data.get("variables", [])
        category = data.get("category", "general")
        tags = data.get("tags", [])

        content = f"[bold yellow]Name:[/bold yellow] {name}\n"
        content += f"[bold cyan]Category:[/bold cyan] {category}\n"
        content += f"[bold green]Description:[/bold green] {description}\n"
        if variables:
            content += f"[bold magenta]Variables:[/bold magenta] {', '.join(variables)}\n"
        if tags:
            content += f"[bold blue]Tags:[/bold blue] {', '.join(tags)}\n"
        content += "\n[bold white]Template:[/bold white]\n"
        content += f"[dim]{template_text}[/dim]"

        panel = Panel(
            content,
            title="[bold white]📄 Random Template[/bold white]",
            border_style="yellow",
        )
        console.print(panel)

    elif result_type == "snippet":
        title = data["title"]
        description = data.get("description", "No description")
        content_text = data["content"]
        category = data.get("category", "general")
        tags = data.get("tags", [])
        use_count = data.get("use_count", 0)

        content = f"[bold yellow]Title:[/bold yellow] {title}\n"
        content += f"[bold cyan]Category:[/bold cyan] {category}\n"
        content += f"[bold green]Description:[/bold green] {description}\n"
        if tags:
            content += f"[bold blue]Tags:[/bold blue] {', '.join(tags)}\n"
        content += f"[bold white]Uses:[/bold white] {use_count}\n\n"
        content += "[bold white]Content:[/bold white]\n"
        content += f"[dim]{content_text}[/dim]"

        panel = Panel(
            content,
            title="[bold white]📋 Random Snippet[/bold white]",
            border_style="cyan",
        )
        console.print(panel)

    console.print(
        f"\n[dim]💡 Tip: Run 'promptc random' again for another random {result_type}[/dim]"
    )


@app.command("tags")
def tags_command(
    action: str = typer.Argument(..., help="Action: suggest, auto-apply, analyze, cleanup"),
    item_id: Optional[str] = typer.Option(None, "--id", help="Item ID for suggestions"),
    source: Optional[str] = typer.Option(
        "favorites", "--source", help="Source type: favorites, prompts"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Smart tags management and suggestions.

    Actions:
    - suggest: Suggest tags for an item
    - auto-apply: Auto-tag all items
    - analyze: Show tag statistics
    - cleanup: Find and remove unused tags
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from app.smart_tags import get_smart_tagger
    import json

    console = Console()
    tagger = get_smart_tagger()

    if action == "suggest":
        if not item_id:
            console.print("[red]Error: --id required for suggest action[/red]")
            raise typer.Exit(1)

        # Suggest tags based on source
        if source == "favorites":
            suggested = tagger.suggest_tags_for_favorite(item_id)
        elif source == "prompts":
            suggested = tagger.suggest_tags_for_prompt(item_id)
        else:
            console.print(f"[red]Unknown source: {source}[/red]")
            raise typer.Exit(1)

        if json_output:
            print(json.dumps({"item_id": item_id, "suggested_tags": suggested}, indent=2))
            return

        if suggested:
            console.print(f"\n[bold cyan]🏷️  Suggested Tags for {item_id}[/bold cyan]")
            for tag in suggested:
                console.print(f"  • [green]{tag}[/green]")
            console.print()
        else:
            console.print(f"[yellow]No new tags to suggest for {item_id}[/yellow]")

    elif action == "auto-apply":
        console.print("\n[bold cyan]🤖 Auto-Tagging Items...[/bold cyan]\n")

        # Auto-tag favorites
        fav_suggestions = tagger.auto_tag_all_favorites(dry_run=dry_run)

        # Auto-tag prompts
        prompt_suggestions = tagger.auto_tag_all_prompts(dry_run=dry_run)

        if json_output:
            print(
                json.dumps(
                    {
                        "favorites": fav_suggestions,
                        "prompts": prompt_suggestions,
                        "dry_run": dry_run,
                    },
                    indent=2,
                )
            )
            return

        total_items = len(fav_suggestions) + len(prompt_suggestions)
        if total_items > 0:
            if dry_run:
                console.print("[yellow]DRY RUN - No changes applied[/yellow]\n")

            console.print(f"[green]Tagged {len(fav_suggestions)} favorites[/green]")
            console.print(f"[green]Tagged {len(prompt_suggestions)} prompts[/green]")
            console.print(f"\n[bold]Total: {total_items} items updated[/bold]")

            if dry_run:
                console.print("\n[dim]Run without --dry-run to apply changes[/dim]")
        else:
            console.print("[yellow]All items already have appropriate tags[/yellow]")

    elif action == "analyze":
        # Get tag statistics
        tag_stats = tagger.get_tag_statistics()
        all_tags = tagger.get_all_tags()

        if json_output:
            print(
                json.dumps(
                    {
                        "total_unique_tags": len(all_tags),
                        "tag_statistics": [
                            {"tag": tag, "count": count} for tag, count in tag_stats
                        ],
                    },
                    indent=2,
                )
            )
            return

        console.print("\n[bold cyan]📊 Tag Analytics[/bold cyan]\n")

        # Summary
        summary = Panel(
            f"[white]Total Unique Tags:[/white] [yellow]{len(all_tags)}[/yellow]\n"
            f"[white]Total Tag Uses:[/white] [green]{sum(count for _, count in tag_stats)}[/green]",
            title="Summary",
            border_style="cyan",
        )
        console.print(summary)
        console.print()

        # Top tags table
        if tag_stats:
            console.print("[bold cyan]🏆 Most Used Tags[/bold cyan]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Rank", style="dim", width=6)
            table.add_column("Tag", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Bar", style="yellow")

            for i, (tag, count) in enumerate(tag_stats[:15], 1):
                bar = "█" * min(count, 30)
                table.add_row(str(i), tag, str(count), bar)

            console.print(table)
            console.print()

        # Show some co-occurrence examples for top tag
        if tag_stats:
            top_tag = tag_stats[0][0]
            cooccur = tagger.get_tag_cooccurrence(top_tag, limit=5)

            if cooccur:
                console.print(f"[bold cyan]🔗 Tags Often Used with '{top_tag}'[/bold cyan]")
                for other_tag, count in cooccur:
                    console.print(f"  • [magenta]{other_tag}[/magenta] [dim]({count} times)[/dim]")
                console.print()

    elif action == "cleanup":
        # Find unused tags
        unused = tagger.find_unused_tags()

        if json_output:
            print(json.dumps({"unused_tags": sorted(list(unused))}, indent=2))
            return

        if unused:
            console.print("\n[bold cyan]🧹 Unused Tags Found[/bold cyan]\n")
            console.print(
                f"[yellow]Found {len(unused)} predefined tags that are not in use:[/yellow]\n"
            )

            for tag in sorted(unused):
                console.print(f"  • [dim]{tag}[/dim]")

            console.print(
                "\n[dim]These tags are defined in patterns but not used in any items[/dim]"
            )
        else:
            console.print("[green]✓ All predefined tags are in use![/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[yellow]Valid actions: suggest, auto-apply, analyze, cleanup[/yellow]")
        raise typer.Exit(1)


@app.command("prompt-compare")
def prompt_compare_command(
    id1: str = typer.Argument(..., help="First prompt ID"),
    id2: str = typer.Argument(..., help="Second prompt ID"),
    source1: str = typer.Option(
        "auto", "--source1", help="Source for first prompt (auto, history, favorites)"
    ),
    source2: str = typer.Option(
        "auto", "--source2", help="Source for second prompt (auto, history, favorites)"
    ),
    unified: bool = typer.Option(
        False, "--unified", "-u", help="Use unified diff format instead of side-by-side"
    ),
):
    """Compare two prompts and show differences.

    Examples:
        promptc prompt-compare prompt1 prompt2
        promptc prompt-compare fav1 fav2 --source1 favorites --source2 favorites
        promptc prompt-compare old-version new-version --unified
    """
    from app.prompt_diff import get_prompt_comparison

    comparison = get_prompt_comparison()
    success = comparison.display_comparison(
        id1, id2, source1=source1, source2=source2, show_side_by_side=not unified
    )

    if not success:
        raise typer.Exit(code=1)


@app.command("prompt-diff")
def prompt_diff_command(
    id1: str = typer.Argument(..., help="First prompt ID"),
    id2: str = typer.Argument(..., help="Second prompt ID"),
    source1: str = typer.Option(
        "auto", "--source1", help="Source for first prompt (auto, history, favorites)"
    ),
    source2: str = typer.Option(
        "auto", "--source2", help="Source for second prompt (auto, history, favorites)"
    ),
    unified: bool = typer.Option(
        True, "--unified/--side-by-side", help="Use unified diff format (default)"
    ),
):
    """Show unified diff between two prompts.

    This is an alias for 'prompt-compare' command with unified diff as default.

    Examples:
        promptc diff prompt1 prompt2
        promptc diff old new --side-by-side
    """
    from app.prompt_diff import get_prompt_comparison

    comparison = get_prompt_comparison()
    success = comparison.display_comparison(
        id1, id2, source1=source1, source2=source2, show_side_by_side=not unified
    )

    if not success:
        raise typer.Exit(code=1)


@app.command("advanced-search")
def advanced_search_command(
    query: Optional[str] = typer.Argument(None, help="Search query text"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language"),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated, favorites only)"
    ),
    start_date: Optional[str] = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    regex: bool = typer.Option(False, "--regex", "-r", help="Use regex matching"),
    fuzzy: bool = typer.Option(False, "--fuzzy", "-f", help="Use fuzzy matching"),
    min_score: Optional[float] = typer.Option(
        None, "--min-score", "-s", help="Minimum score threshold"
    ),
    max_results: int = typer.Option(50, "--limit", "-n", help="Maximum results per source"),
    source: str = typer.Option("all", "--source", help="Search source (all, history, favorites)"),
    full_text: bool = typer.Option(
        False, "--full", help="Show full prompt text instead of truncated"
    ),
):
    """Advanced search for prompts with multiple filters.

    Search through history and favorites with powerful filtering options.

    Examples:
        promptc advanced-search "machine learning"
        promptc advanced-search --domain coding --language python
        promptc advanced-search "API.*endpoint" --regex
        promptc advanced-search "machne lerning" --fuzzy
        promptc advanced-search --from 2025-01-01 --to 2025-12-31
        promptc advanced-search --tags python,api --source favorites
        promptc advanced-search "test" --min-score 0.8 --limit 10
    """
    from app.advanced_search import get_advanced_search

    search_engine = get_advanced_search()

    # Parse tags if provided
    tag_list = tags.split(",") if tags else None

    # Perform search based on source
    if source == "history":
        results = {
            "history": search_engine.search_history(
                query=query,
                domain=domain,
                language=language,
                start_date=start_date,
                end_date=end_date,
                use_regex=regex,
                use_fuzzy=fuzzy,
                min_score=min_score,
                max_results=max_results,
            ),
            "favorites": [],
        }
    elif source == "favorites":
        results = {
            "history": [],
            "favorites": search_engine.search_favorites(
                query=query,
                domain=domain,
                language=language,
                tags=tag_list,
                start_date=start_date,
                end_date=end_date,
                use_regex=regex,
                use_fuzzy=fuzzy,
                min_score=min_score,
                max_results=max_results,
            ),
        }
    else:  # all
        results = search_engine.search_all(
            query=query,
            domain=domain,
            language=language,
            tags=tag_list,
            start_date=start_date,
            end_date=end_date,
            use_regex=regex,
            use_fuzzy=fuzzy,
            min_score=min_score,
            max_results=max_results,
        )

    search_engine.display_results(results, show_full_text=full_text)


@app.command("stats")
def stats_command(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed statistics"),
    compact: bool = typer.Option(False, "--compact", "-c", help="Show compact table view"),
):
    """Display prompt statistics and counters.

    Shows quick overview of your prompt collection including counts,
    recent activity, quality metrics, and top domains.

    Examples:
        promptc stats
        promptc stats --detailed
        promptc stats --compact
    """
    from app.quick_stats import get_quick_stats

    stats = get_quick_stats()

    if detailed:
        stats.display_full_stats()
    elif compact:
        stats.display_compact_table()
    else:
        # Default: show banner
        from rich.console import Console

        console = Console()
        banner = stats.create_banner(compact=False)
        console.print(f"\n{banner}\n")


@app.command("export-prompts")
def export_prompts_command(
    output: str = typer.Argument(..., help="Output file path"),
    source: str = typer.Option(
        "all", "--source", "-s", help="Source to export: history, favorites, all"
    ),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, csv"),
    pretty: bool = typer.Option(
        True, "--pretty/--compact", help="Pretty print JSON (default: pretty)"
    ),
):
    """Export prompts to JSON or CSV format.

    Export your prompt history and favorites to external files for backup,
    sharing, or migration purposes.

    Examples:
        promptc export-prompts backup.json
        promptc export-prompts backup.json --source favorites
        promptc export-prompts backup.csv --format csv
        promptc export-prompts backup.json --source history --compact
    """
    from pathlib import Path
    from app.export_import import get_export_import_manager
    from rich.console import Console

    console = Console()
    manager = get_export_import_manager()
    output_path = Path(output).resolve()

    # Validate source
    if source not in ["history", "favorites", "all"]:
        console.print(
            f"[red]❌ Error:[/red] Invalid source '{source}'. Use: history, favorites, or all"
        )
        raise typer.Exit(1)

    # Validate format
    if format not in ["json", "csv"]:
        console.print(f"[red]❌ Error:[/red] Invalid format '{format}'. Use: json or csv")
        raise typer.Exit(1)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        console.print(f"\n[cyan]📦 Exporting {source} to {format.upper()}...[/cyan]\n")

        if format == "json":
            stats = manager.export_to_json(output_path, source=source, pretty=pretty)
        else:  # csv
            stats = manager.export_to_csv(output_path, source=source)

        manager.display_export_summary(stats, format, output_path)

    except Exception as e:
        console.print(f"\n[red]❌ Export failed:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("import-prompts")
def import_prompts_command(
    input: str = typer.Argument(..., help="Input file path"),
    target: str = typer.Option("auto", "--target", "-t", help="Target: history, favorites, auto"),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing data (default: merge)"
    ),
):
    """Import prompts from JSON or CSV format.

    Import previously exported prompt data back into PromptC. Can merge with
    existing data or replace it completely.

    Examples:
        promptc import-prompts backup.json
        promptc import-prompts backup.json --target favorites
        promptc import-prompts backup.csv --replace
        promptc import-prompts data.json --target history --merge
    """
    from pathlib import Path
    from app.export_import import get_export_import_manager
    from rich.console import Console

    console = Console()
    manager = get_export_import_manager()
    input_path = Path(input).resolve()

    # Validate target
    if target not in ["history", "favorites", "auto"]:
        console.print(
            f"[red]❌ Error:[/red] Invalid target '{target}'. Use: history, favorites, or auto"
        )
        raise typer.Exit(1)

    # Check if file exists
    if not input_path.exists():
        console.print(f"[red]❌ Error:[/red] File not found: {input_path}")
        raise typer.Exit(1)

    # Detect format from extension
    format_type = "json" if input_path.suffix.lower() == ".json" else "csv"

    try:
        mode_text = "Merging" if merge else "Replacing"
        console.print(f"\n[cyan]📥 {mode_text} data from {format_type.upper()}...[/cyan]\n")

        if format_type == "json":
            stats = manager.import_from_json(input_path, target=target, merge=merge)
        else:  # csv
            stats = manager.import_from_csv(input_path, target=target, merge=merge)

        manager.display_import_summary(stats, format_type, merge)

    except Exception as e:
        console.print(f"\n[red]❌ Import failed:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("templates")
def templates_command(
    action: str = typer.Argument(..., help="Action: list, show, use, categories"),
    template_id: Optional[str] = typer.Option(None, "--id", "-i", help="Template ID"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """Manage and use prompt templates.

    Quick access to ready-made prompt templates for common tasks like
    code review, brainstorming, email writing, and more.

    Actions:
        list        - List all available templates
        show        - Show template details (requires --id)
        use         - Use a template (requires --id)
        categories  - List all categories

    Examples:
        promptc templates list
        promptc templates list --category development
        promptc templates show --id code-review
        promptc templates use --id brainstorm
        promptc templates categories
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt
    from app.templates import get_registry

    console = Console()
    registry = get_registry()

    if action == "list":
        templates = registry.list_templates(category=category)

        if not templates:
            if category:
                console.print(f"\n[yellow]📚 No templates found in category: {category}[/yellow]\n")
            else:
                console.print("\n[yellow]📚 No templates available[/yellow]\n")
            return

        table = Table(title="📚 Available Templates", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan", width=20)
        table.add_column("Name", style="green", width=25)
        table.add_column("Category", style="magenta", width=15)
        table.add_column("Description", style="white")

        for template in templates:
            table.add_row(
                template.id,
                template.name,
                template.category,
                template.description,
            )

        console.print()
        console.print(table)
        console.print(
            "\n[dim]💡 Use 'promptc templates show --id <template-id>' for details[/dim]\n"
        )

    elif action == "show":
        if not template_id:
            console.print("[red]❌ Error:[/red] --id required for show action")
            raise typer.Exit(1)

        template = registry.get_template(template_id)
        if not template:
            console.print(f"\n[red]❌ Template not found:[/red] {template_id}\n")
            return

        # Create info panel
        info_text = f"[bold cyan]Name:[/bold cyan] {template.name}\n"
        info_text += f"[bold cyan]Category:[/bold cyan] {template.category}\n"
        info_text += f"[bold cyan]Description:[/bold cyan] {template.description}\n"
        info_text += f"[bold cyan]Version:[/bold cyan] {template.version}\n"

        if template.author:
            info_text += f"[bold cyan]Author:[/bold cyan] {template.author}\n"

        info_text += "\n[bold yellow]Variables:[/bold yellow]\n"
        for var in template.variables:
            required = "[red]*[/red]" if var.required else "[dim](optional)[/dim]"
            default = f" [dim](default: {var.default})[/dim]" if var.default else ""
            info_text += f"  • {{{{{var.name}}}}} {required} - {var.description}{default}\n"

        if template.tags:
            info_text += f"\n[bold magenta]Tags:[/bold magenta] {', '.join(template.tags)}"

        # Template preview
        template_preview = template.template_text
        if len(template_preview) > 400:
            template_preview = template_preview[:400] + "..."

        console.print()
        console.print(Panel(info_text, title=f"📝 Template: {template_id}", border_style="cyan"))
        console.print()
        console.print(
            Panel(
                template_preview,
                title="Template Preview",
                border_style="green",
                subtitle="(truncated)" if len(template.template_text) > 400 else None,
            )
        )

        if template.example_values:
            console.print()
            console.print("[bold]Example Values:[/bold]")
            for key, value in template.example_values.items():
                console.print(f"  [cyan]{key}:[/cyan] {value}")

        console.print(
            f"\n[dim]💡 Use 'promptc templates use --id {template_id}' to use this template[/dim]\n"
        )

    elif action == "use":
        if not template_id:
            console.print("[red]❌ Error:[/red] --id required for use action")
            raise typer.Exit(1)

        template = registry.get_template(template_id)
        if not template:
            console.print(f"\n[red]❌ Template not found:[/red] {template_id}\n")
            return

        console.print(f"\n[bold cyan]📝 Using template:[/bold cyan] {template.name}\n")

        # Collect variable values
        variables = {}
        for var in template.variables:
            prompt_text = f"[cyan]{var.name}[/cyan]"
            if var.description:
                prompt_text += f" [dim]({var.description})[/dim]"
            if var.default:
                prompt_text += f" [dim](default: {var.default})[/dim]"
            if not var.required:
                prompt_text += " [dim](optional)[/dim]"

            value = Prompt.ask(prompt_text, default=var.default or "")
            if value:
                variables[var.name] = value

        # Render template
        try:
            rendered = template.render(variables)
            console.print("\n[bold green]✅ Template rendered successfully![/bold green]\n")
            console.print(Panel(rendered, title="Rendered Output", border_style="green"))
            console.print()

            # Ask if user wants to save or use it
            save_choice = Prompt.ask(
                "\n[cyan]What would you like to do?[/cyan]",
                choices=["copy", "compile", "save", "cancel"],
                default="compile",
            )

            if save_choice == "compile":
                # Use the rendered output as input for compilation
                from app.compiler import get_compiler

                compiler = get_compiler()
                result = compiler.compile(rendered)

                console.print("\n[bold green]✅ Compiled successfully![/bold green]\n")
                console.print(Panel(result.prompt, title="Compiled Prompt", border_style="green"))

            elif save_choice == "save":
                # Save to a file
                filename = Prompt.ask("[cyan]Filename[/cyan]", default=f"{template_id}-output.txt")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(rendered)
                console.print(f"\n[green]✅ Saved to {filename}[/green]\n")

            elif save_choice == "copy":
                console.print("\n[yellow]📋 Copy the output above to clipboard[/yellow]\n")

        except ValueError as e:
            console.print(f"\n[red]❌ Error:[/red] {str(e)}\n")
            raise typer.Exit(1)

    elif action == "categories":
        categories = registry.get_categories()

        if not categories:
            console.print("\n[yellow]📚 No categories available[/yellow]\n")
            return

        console.print("\n[bold cyan]📂 Template Categories:[/bold cyan]\n")
        for cat in categories:
            count = len(registry.list_templates(category=cat))
            console.print(f"  • [cyan]{cat}[/cyan] [dim]({count} templates)[/dim]")

        console.print("\n[dim]💡 Use 'promptc templates list --category <name>' to filter[/dim]\n")

    else:
        console.print(f"[red]❌ Unknown action:[/red] {action}")
        console.print("[yellow]Valid actions:[/yellow] list, show, use, categories")
        raise typer.Exit(1)


# Entry point
if __name__ == "__main__":  # pragma: no cover
    app()
