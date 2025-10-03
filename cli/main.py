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
from app.templates import get_registry, PromptTemplate, TemplateVariable
from app.validator import validate_prompt
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
app.add_typer(rag_app, name="rag")
app.add_typer(plugins_app, name="plugins")
app.add_typer(template_app, name="template")


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
# Template subcommands
# --------------


@template_app.command("list")
def template_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all available prompt templates."""
    registry = get_registry()
    templates = registry.list_templates(category=category)

    if json_out:
        data = [t.to_dict() for t in templates]
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not templates:
        typer.echo("No templates found.")
        if category:
            typer.echo("Try without --category filter or check available categories.")
        return

    # Group by category
    by_category: dict[str, list] = {}
    for t in templates:
        by_category.setdefault(t.category, []).append(t)

    for cat, tmpl_list in sorted(by_category.items()):
        print(f"\n[bold cyan]{cat}[/bold cyan]")
        for t in tmpl_list:
            tags_str = f" [{', '.join(t.tags)}]" if t.tags else ""
            print(f"  • [green]{t.id}[/green] - {t.name}{tags_str}")
            print(f"    {t.description}")


@template_app.command("show")
def template_show(
    template_id: str = typer.Argument(..., help="Template ID to display"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
    show_example: bool = typer.Option(
        False, "--example", "-e", help="Show example variable values"
    ),
):
    """Show details of a specific template."""
    registry = get_registry()
    template = registry.get_template(template_id)

    if not template:
        typer.secho(f"Template '{template_id}' not found.", fg=typer.colors.RED)
        typer.echo("Run 'promptc template list' to see available templates.")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(template.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"\n[bold]{template.name}[/bold] (ID: [cyan]{template.id}[/cyan])")
    print(f"Category: {template.category}")
    print(f"Version: {template.version}")
    if template.author:
        print(f"Author: {template.author}")
    if template.tags:
        print(f"Tags: {', '.join(template.tags)}")
    print(f"\n{template.description}")

    print("\n[bold]Variables:[/bold]")
    for var in template.variables:
        req_str = " (required)" if var.required else " (optional)"
        default_str = f" [default: {var.default}]" if var.default else ""
        var_syntax = "{{" + var.name + "}}"
        print(f"  • [green]{var_syntax}[/green]{req_str}{default_str}")
        print(f"    {var.description}")

    if show_example and template.example_values:
        print("\n[bold]Example values:[/bold]")
        for key, value in template.example_values.items():
            val_preview = value[:60] + "..." if len(value) > 60 else value
            print(f"  {key}: {val_preview}")

    print("\n[bold]Template:[/bold]")
    print(template.template_text[:500] + ("..." if len(template.template_text) > 500 else ""))


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


@template_app.command("create")
def template_create(
    template_id: str = typer.Argument(..., help="Unique ID for the template"),
    name: str = typer.Option(..., "--name", "-n", help="Template name"),
    description: str = typer.Option(..., "--desc", "-d", help="Template description"),
    category: str = typer.Option(..., "--category", "-c", help="Template category"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Load template text from file"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive variable definition"
    ),
):
    """Create a new user template."""
    registry = get_registry()

    # Check if template already exists
    existing = registry.get_template(template_id)
    if existing:
        typer.secho(
            f"Template '{template_id}' already exists. Choose a different ID.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Get template text
    if from_file:
        if not from_file.exists():
            typer.secho(f"File not found: {from_file}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        template_text = from_file.read_text(encoding="utf-8")
    else:
        typer.echo("Enter template text (use {{variable}} for placeholders):")
        typer.echo("Press Ctrl+D (Unix) or Ctrl+Z then Enter (Windows) when done:")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        template_text = "\n".join(lines)

    # Extract variables from template
    var_pattern = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")
    var_names = set(var_pattern.findall(template_text))

    variables: List[TemplateVariable] = []

    if interactive and var_names:
        typer.echo(f"\nFound {len(var_names)} variables. Define them:")
        for var_name in sorted(var_names):
            var_desc = typer.prompt(f"  Description for '{var_name}'", default="")
            var_required = typer.confirm(f"  Is '{var_name}' required?", default=True)
            var_default = None
            if not var_required:
                var_default = typer.prompt(
                    f"  Default value for '{var_name}'", default="", show_default=False
                )
                var_default = var_default or None

            variables.append(
                TemplateVariable(
                    name=var_name,
                    description=var_desc or f"Value for {var_name}",
                    default=var_default,
                    required=var_required,
                )
            )
    else:
        # Auto-create basic variables
        for var_name in sorted(var_names):
            variables.append(
                TemplateVariable(
                    name=var_name,
                    description=f"Value for {var_name}",
                    required=True,
                )
            )

    # Create template
    template = PromptTemplate(
        id=template_id,
        name=name,
        description=description,
        category=category,
        template_text=template_text,
        variables=variables,
    )

    # Save template
    saved_path = registry.save_template(template, user_template=True)
    print(f"[bold green]Template created:[/bold green] {template_id}")
    print(f"[saved] {saved_path}")
    typer.echo(f"\nUse it with: promptc template apply {template_id}")


@template_app.command("delete")
def template_delete(
    template_id: str = typer.Argument(..., help="Template ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a user template."""
    registry = get_registry()

    template = registry.get_template(template_id)
    if not template:
        typer.secho(f"Template '{template_id}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not force:
        confirm = typer.confirm(f"Delete template '{template.name}' ({template_id})?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

    success = registry.delete_template(template_id, user_only=True)

    if success:
        print(f"[bold green]Deleted:[/bold green] {template_id}")
    else:
        typer.secho(
            "Could not delete template (may be a built-in template).", fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)


@template_app.command("categories")
def template_categories(
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all template categories."""
    registry = get_registry()
    categories = registry.get_categories()

    if json_out:
        typer.echo(json.dumps(categories, ensure_ascii=False, indent=2))
        return

    if not categories:
        typer.echo("No categories found.")
        return

    print("[bold]Template Categories:[/bold]")
    for cat in categories:
        count = len(registry.list_templates(category=cat))
        print(f"  • [cyan]{cat}[/cyan] ({count} templates)")


@app.command("validate-prompt")
def validate_prompt_command(
    text: List[str] = typer.Argument(None, help="Prompt text to validate"),
    from_file: Optional[Path] = typer.Option(None, "--from-file", "-f", help="Read prompt from file"),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin"),
    show_suggestions: bool = typer.Option(True, "--suggestions/--no-suggestions", help="Show improvement suggestions"),
    show_strengths: bool = typer.Option(True, "--strengths/--no-strengths", help="Show prompt strengths"),
    min_score: Optional[float] = typer.Option(None, "--min-score", help="Fail if score below threshold (0-100)"),
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
        lines.append(f"[bold]Overall Score:[/bold] [{total_color}]{score.total:.1f}/100[/{total_color}]\n")
        lines.append("[bold]Breakdown:[/bold]")
        lines.append(f"  • Clarity:       {score.clarity:.1f}/100")
        lines.append(f"  • Specificity:   {score.specificity:.1f}/100")
        lines.append(f"  • Completeness:  {score.completeness:.1f}/100")
        lines.append(f"  • Consistency:   {score.consistency:.1f}/100\n")

        # Issues section
        if result.issues:
            lines.append(f"[bold]Issues Found:[/bold] {result.errors} errors, {result.warnings} warnings, {result.info} info\n")
            for issue in result.issues:
                severity_color = {"error": "red", "warning": "yellow", "info": "blue"}[issue.severity]
                icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}[issue.severity]
                lines.append(f"[{severity_color}]{icon} {issue.severity.upper()}[/{severity_color}] ({issue.category})")
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
            clean_output = re.sub(r'\[/?[a-z0-9 ]+\]', '', output)
            out.write_text(clean_output, encoding="utf-8")
            typer.echo(f"Validation report saved to {out}")
        else:
            print(output)

    # Exit with error code if below min_score
    if min_score is not None and result.score.total < min_score:
        typer.echo(f"\nValidation failed: Score {result.score.total:.1f} < {min_score}", err=True)
        raise typer.Exit(1)


# Entry point
if __name__ == "__main__":  # pragma: no cover
    app()
