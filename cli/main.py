from __future__ import annotations
import json
from typing import List, Any, Optional
from pathlib import Path
import typer
from rich import print
import difflib
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
app.add_typer(rag_app, name="rag")


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
    if not text and not from_file:
        raise typer.BadParameter("Provide TEXT or --from-file")
    if from_file is not None:
        try:
            full_text = from_file.read_text(encoding="utf-8")
        except Exception as e:
            raise typer.BadParameter(f"Cannot read file: {from_file} ({e})")
    else:
        full_text = " ".join(text)
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
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: yaml|json (default json)"
    ),
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
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l:
        if fmt_l in {"yaml", "yml"} and yaml is not None:  # type: ignore
            typer.echo(yaml.safe_dump(res, sort_keys=False, allow_unicode=True))  # type: ignore
        else:
            typer.echo(json.dumps(res, ensure_ascii=False, indent=2))
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
        None, "--format", help="Output format: yaml|json (default json)"
    ),
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
    if json_out or fmt_l:
        if fmt_l in {"yaml", "yml"} and yaml is not None:  # type: ignore
            typer.echo(yaml.safe_dump(packed, sort_keys=False, allow_unicode=True))  # type: ignore
        else:
            typer.echo(json.dumps(packed, ensure_ascii=False, indent=2))
    else:
        print(packed.get("packed", ""))


@rag_app.command("stats")
def rag_stats(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: yaml|json (default json)"
    ),
):
    s = rag_stats_fn(db_path=str(db_path) if db_path else None)
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l:
        if fmt_l in {"yaml", "yml"} and yaml is not None:  # type: ignore
            typer.echo(yaml.safe_dump(s, sort_keys=False, allow_unicode=True))  # type: ignore
        else:
            typer.echo(json.dumps(s, ensure_ascii=False, indent=2))
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
):
    r = rag_prune_fn(db_path=str(db_path) if db_path else None)
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l:
        if fmt_l in {"yaml", "yml"} and yaml is not None:  # type: ignore
            typer.echo(yaml.safe_dump(r, sort_keys=False, allow_unicode=True))  # type: ignore
        else:
            typer.echo(json.dumps(r, ensure_ascii=False, indent=2))
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
):
    try:
        data = _json.loads(file.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    cur: Any = data
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            typer.secho("<not-found>", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
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
):
    try:
        ja = _json.loads(a.read_text(encoding="utf-8"))
        jb = _json.loads(b.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    sa = _json.dumps(ja, ensure_ascii=False, indent=2).splitlines(keepends=False)
    sb = _json.dumps(jb, ensure_ascii=False, indent=2).splitlines(keepends=False)
    diff = difflib.unified_diff(sa, sb, fromfile=str(a), tofile=str(b), n=context)
    out = "".join(line + "\n" if not line.endswith("\n") else line for line in diff)
    # Print even if empty; tests expect some output for different inputs
    typer.echo(out)


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
):
    if not in_dir.exists() or not in_dir.is_dir():
        raise typer.BadParameter(f"Input dir not found: {in_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = (format or "json").lower()
    if fmt not in {"json", "md", "yaml", "yml"}:
        raise typer.BadParameter("--format must be json, md or yaml")
    out_ext = "json" if fmt == "json" else ("md" if fmt == "md" else "yaml")
    # Suppress per-file saved logs for cleaner output
    setattr(_write_output, "_suppress_log", True)  # type: ignore
    try:
        files = sorted([p for p in in_dir.glob("*.txt") if p.is_file()])
        for src in files:
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
    finally:
        # Re-enable logging for other commands
        setattr(_write_output, "_suppress_log", False)  # type: ignore


# Entry point
if __name__ == "__main__":  # pragma: no cover
    app()
