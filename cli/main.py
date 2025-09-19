from __future__ import annotations
import json
from typing import List, Any, Optional
from pathlib import Path
import typer
from rich import print
import difflib
import json as _json
from jsonschema import Draft202012Validator
from app.compiler import compile_text, compile_text_v2, optimize_ir, HEURISTIC_VERSION, HEURISTIC2_VERSION, generate_trace
from app.emitters import (
    emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt,
    emit_system_prompt_v2, emit_user_prompt_v2, emit_plan_v2, emit_expanded_prompt_v2,
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
    system_prompt = emit_system_prompt(ir) if ir else (emit_system_prompt_v2(ir2) if (ir2 and render_v2) else "")
    if quiet:
        print(system_prompt)
        return
    user_prompt = emit_user_prompt(ir) if ir else (emit_user_prompt_v2(ir2) if (ir2 and render_v2) else "")
    plan = emit_plan(ir) if ir else (emit_plan_v2(ir2) if (ir2 and render_v2) else "")
    expanded = emit_expanded_prompt(ir, diagnostics=diagnostics) if ir else (emit_expanded_prompt_v2(ir2, diagnostics=diagnostics) if (ir2 and render_v2) else "")
    if json_only:
        data = ir.model_dump() if ir else ir2.model_dump()
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
    ir_json = ir.model_dump() if ir else ir2.model_dump()
    if trace and ir:
        ir_json['trace'] = generate_trace(ir)
    rendered = json.dumps(ir_json, ensure_ascii=False, indent=2)
    if out or out_dir:
        # Support --format md to save prompts as Markdown (v1 or v2 rendering)
        if fmt and fmt.lower() == 'md' and (ir or (ir2 and render_v2)):
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
        # Allow specifying full filename and ensure parent exists
        target = out
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        directory = out_dir or Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / default_name
    target.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    # Quiet for internal batch metrics; still show path when invoked directly
    if not getattr(_write_output, '_suppress_log', False):  # type: ignore
        print(f"[saved] {target}")

@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    """Top-level CLI. Shows help when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

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

@app.command()
def version():
    """Print package version."""
    print(get_version())


def _schema_path(v2: bool) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "schema" / ("ir_v2.schema.json" if v2 else "ir.schema.json")


@app.command()
def validate(
    files: List[Path] = typer.Argument(..., help="IR JSON file(s) to validate"),
    v2: bool = typer.Option(True, "--v2/--v1", help="Validate against IR v2 (default) or IR v1 schema"),
):
    """Validate IR JSON file(s) against the schema."""
    schema_file = _schema_path(v2)
    try:
        schema = _json.loads(schema_file.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Cannot load schema: {schema_file} ({e})", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    validator = Draft202012Validator(schema)
    failed = 0
    ok = 0
    for f in files:
        try:
            data = _json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            typer.secho(f"[read-error] {f}: {e}", err=True, fg=typer.colors.RED)
            failed += 1
            continue
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            failed += 1
            typer.secho(f"[invalid] {f}", err=True, fg=typer.colors.RED)
            for err in errors[:5]:  # show first few
                loc = ".".join(str(p) for p in err.path) or "<root>"
                typer.secho(f"  at {loc}: {err.message}", err=True, fg=typer.colors.RED)
        else:
            typer.secho(f"[ok] {f}", fg=typer.colors.GREEN)
        ok += 1
    typer.secho(f"Summary: ok={ok} invalid={failed}", fg=(typer.colors.GREEN if failed==0 else typer.colors.YELLOW))
    if failed:
        raise typer.Exit(code=1)


@app.command()
def diff(
    a: Path = typer.Argument(..., help="First IR JSON file"),
    b: Path = typer.Argument(..., help="Second IR JSON file"),
):
    """Show a unified diff between two IR JSON files."""
    try:
        aj = _json.loads(a.read_text(encoding="utf-8"))
        bj = _json.loads(b.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    a_txt = _json.dumps(aj, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=False)
    b_txt = _json.dumps(bj, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=False)
    diff_lines = list(difflib.unified_diff(a_txt, b_txt, fromfile=str(a), tofile=str(b), lineterm=""))
    if not diff_lines:
        print("No differences.")
        return
    print("\n".join(diff_lines))


@app.command()
def batch(
    in_dir: Path = typer.Argument(..., help="Input directory containing .txt files"),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory to write outputs"),
    pattern: str = typer.Option("*.txt", "--pattern", help="Glob pattern for input files"),
    name_template: str = typer.Option("{stem}.{ext}", "--name-template", help="Output filename template (placeholders: {stem} {ext} {ts})"),
    concurrency: int = typer.Option(1, "--concurrency", min=1, help="Number of files to compile in parallel (threads)"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Include diagnostics in expanded output"),
    persona: str = typer.Option(None, "--persona", help="Force persona"),
    trace: bool = typer.Option(False, "--trace", help="Include heuristic trace in IR v1 JSON"),
    v1: bool = typer.Option(False, "--v1", help="Use legacy IR v1"),
    render_v2: bool = typer.Option(False, "--render-v2", help="Render prompts with IR v2 emitters"),
    format: str = typer.Option("json", "--format", help="Output format: json|md"),
):
    """Compile all matching files in a directory."""
    files = sorted(in_dir.glob(pattern))
    if not files:
        typer.secho("No input files found.", err=True, fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    out_dir.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ext_is_md = (format and format.lower() == "md")
    tasks = []

    def prepare(f: Path):
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as e:
            typer.secho(f"Skip {f}: {e}", err=True, fg=typer.colors.RED)
            return None
        ext = "md" if ext_is_md else "json"
        ts = _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        try:
            fname = name_template.format(stem=f.stem, ext=ext, ts=ts)
        except Exception:
            fname = f"{f.stem}.{ext}"
        target = out_dir / fname
        return (text, ext, target)

    for f in files:
        prep = prepare(f)
        if prep:
            tasks.append(prep)

    start = _time.time()
    per_times: list[float] = []

    def worker(args):  # type: ignore
        text, ext, target = args
        t0 = _time.time()
        # Suppress individual save logs for cleaner batch output
        setattr(_write_output, '_suppress_log', True)
        try:
            _run_compile(
                text,
                diagnostics=diagnostics,
                json_only=(ext == "json"),
                quiet=False,
                persona=persona,
                trace=trace,
                v1=v1,
                render_v2=render_v2,
                out=target,
                out_dir=None,
                fmt=format,
            )
        finally:
            setattr(_write_output, '_suppress_log', False)
        return _time.time() - t0

    if concurrency > 1 and len(tasks) > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(worker, t) for t in tasks]
            for fut in as_completed(futures):
                try:
                    per_times.append(fut.result())
                except Exception as e:
                    typer.secho(f"[worker-error] {e}", err=True, fg=typer.colors.RED)
    else:
        for t in tasks:
            try:
                per_times.append(worker(t))
            except Exception as e:
                typer.secho(f"[worker-error] {e}", err=True, fg=typer.colors.RED)

    total = (_time.time() - start) * 1000
    avg = (sum(per_times) / len(per_times) * 1000) if per_times else 0.0
    print(f"[done] {len(tasks)} files -> {out_dir} in {int(total)} ms (avg {avg:.1f} ms) concurrency={concurrency}")


def _jsonpath_get(data: Any, path: str) -> Any:
    cur: Any = data
    for part in path.split('.'):
        if part == '':
            continue
        # list index?
        try:
            idx = int(part)
            cur = cur[idx]
        except ValueError:
            # dict key
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                raise KeyError(part)
        except Exception as e:  # index errors
            raise KeyError(part) from e
    return cur


@app.command("json-path")
def json_path(
    file: Path = typer.Argument(..., help="IR JSON file"),
    path: str = typer.Argument(..., help="Dot path (e.g., metadata.domain_confidence or constraints.0.priority)"),
    raw: bool = typer.Option(False, "--raw", help="Print raw scalar (no JSON quoting) when value is str/int/float/bool"),
):
    """Print a value from IR JSON using a simple dot path (supports list indices)."""
    try:
        data = _json.loads(file.read_text(encoding="utf-8"))
    except Exception as e:
        typer.secho(f"Read error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    try:
        val = _jsonpath_get(data, path)
    except KeyError:
        typer.secho(f"Path not found: {path}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if raw and isinstance(val, (str, int, float, bool)):
        print(val)
    else:
        print(_json.dumps(val, ensure_ascii=False))


@rag_app.command("index")
def rag_index(
    paths: List[Path] = typer.Argument(..., help="Files or directories to ingest"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Path to SQLite index (defaults to ~/.promptc_index.db)"),
    ext: Optional[List[str]] = typer.Option(None, "--ext", help="File extensions to include (repeatable), e.g., --ext .txt --ext .md"),
    embed: bool = typer.Option(False, "--embed", help="Compute & store tiny deterministic embeddings for chunks"),
    embed_dim: int = typer.Option(64, "--embed-dim", help="Embedding dimension (only for --embed)"),
):
    """Ingest files/dirs into a local full-text (and optional embedding) index."""
    n_docs, n_chunks, secs = ingest_paths(
        [str(p) for p in paths],
        db_path=str(db_path) if db_path else None,
        exts=ext,
        embed=embed,
        embed_dim=embed_dim,
    )
    target_db = str(db_path) if db_path else DEFAULT_DB_PATH
    ms = int(secs * 1000)
    mode = "fts+embed" if embed else "fts"
    print(f"[indexed:{mode}] {n_docs} docs, {n_chunks} chunks in {ms} ms -> {target_db}")


@rag_app.command("query")
def rag_query(
    query: List[str] = typer.Argument(..., help="Search query (use quotes for multi-word)"),
    k: int = typer.Option(5, "--k", help="Top-K results"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Path to SQLite index (defaults to ~/.promptc_index.db)"),
    method: str = typer.Option("fts", "--method", help="Retrieval method: fts|embed|hybrid"),
    embed_dim: int = typer.Option(64, "--embed-dim", help="Embedding dimension (must match ingest)"),
    alpha: float = typer.Option(0.5, "--alpha", help="Hybrid weighting (fts vs embed)"),
    json_only: bool = typer.Option(False, "--json", help="Output raw JSON results"),
):
    """Search index using fts, embeddings, or hybrid fusion."""
    q = " ".join(query)
    method_norm = method.lower()
    if method_norm not in {"fts", "embed", "hybrid"}:
        raise typer.BadParameter("--method must be one of: fts, embed, hybrid")
    dbp = str(db_path) if db_path else None
    if method_norm == "embed":
        results = search_embed(q, k=k, db_path=dbp, embed_dim=embed_dim)
    elif method_norm == "hybrid":
        results = search_hybrid(q, k=k, db_path=dbp, embed_dim=embed_dim, alpha=alpha)
    else:
        results = search(q, k=k, db_path=dbp)
    if json_only:
        typer.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        print("No results.")
        return
    for i, r in enumerate(results, start=1):
        if method_norm == "embed" and "similarity" in r:
            sim = f"{r['similarity']:.3f}"
            print(f"[{i}] sim={sim} {r['path']}#{r['chunk_index']}: {r['snippet']}")
        elif method_norm == "hybrid" and "hybrid_score" in r:
            hs = f"{r['hybrid_score']:.3f}"
            sim = f"{r.get('similarity', 0):.3f}" if 'similarity' in r else '-'
            print(f"[{i}] hybrid={hs} sim={sim} {r['path']}#{r['chunk_index']}: {r['snippet']}")
        else:
            score = f"{r['score']:.3f}" if isinstance(r.get('score'), (int, float)) else str(r.get('score'))
            print(f"[{i}] score={score} {r['path']}#{r['chunk_index']}: {r['snippet']}")


@rag_app.command("pack")
def rag_pack(
    query: List[str] = typer.Argument(..., help="Query text (used for metadata only)"),
    k: int = typer.Option(8, "--k", help="Top-K to retrieve before packing"),
    max_chars: int = typer.Option(4000, "--max-chars", help="Character budget for packed context"),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Approx token budget; overrides max-chars when set"),
    token_ratio: float = typer.Option(4.0, "--token-ratio", help="Chars per token heuristic (default 4.0)"),
    method: str = typer.Option("hybrid", "--method", help="Retrieval method fts|embed|hybrid"),
    embed_dim: int = typer.Option(64, "--embed-dim", help="Embedding dimension (for embed/hybrid)"),
    alpha: float = typer.Option(0.5, "--alpha", help="Hybrid weighting"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Path to SQLite index"),
    json_only: bool = typer.Option(False, "--json", help="Print packed JSON only"),
):
    """Retrieve then pack top-K chunks into a single context under a char budget."""
    q = " ".join(query)
    dbp = str(db_path) if db_path else None
    method_norm = method.lower()
    if method_norm not in {"fts", "embed", "hybrid"}:
        raise typer.BadParameter("--method must be fts|embed|hybrid")
    if method_norm == "embed":
        res = search_embed(q, k=k, db_path=dbp, embed_dim=embed_dim)
    elif method_norm == "hybrid":
        res = search_hybrid(q, k=k, db_path=dbp, embed_dim=embed_dim, alpha=alpha)
    else:
        res = search(q, k=k, db_path=dbp)
    packed = pack_context(q, res, max_chars=max_chars, max_tokens=max_tokens, token_chars=token_ratio)
    if json_only:
        typer.echo(json.dumps(packed, ensure_ascii=False, indent=2))
        return
    toks = packed.get('tokens')
    if toks is not None:
        print(f"[packed] tokens={toks} chars={packed['chars']} included={len(packed['included'])}")
    else:
        print(f"[packed] chars={packed['chars']} included={len(packed['included'])}")
    print(packed['packed'])


@rag_app.command("stats")
def rag_stats(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Path to SQLite index (defaults to ~/.promptc_index.db)"),
    json_only: bool = typer.Option(False, "--json", help="Print raw JSON stats"),
):
    """Show index statistics (docs, chunks, sizes, largest files)."""
    s = rag_stats_fn(db_path=str(db_path) if db_path else None)
    if json_only:
        typer.echo(json.dumps(s, ensure_ascii=False, indent=2))
        return
    print(f"docs={s['docs']} chunks={s['chunks']} total_bytes={s['total_bytes']} avg_bytes={int(s['avg_bytes'])}")
    if s['largest']:
        print("largest:")
        for entry in s['largest']:
            print(f"  {entry['size']:>8}  {entry['path']}")


@rag_app.command("prune")
def rag_prune(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="Path to SQLite index (defaults to ~/.promptc_index.db)"),
    json_only: bool = typer.Option(False, "--json", help="Print raw JSON result"),
):
    """Remove records for files that no longer exist on disk."""
    res = rag_prune_fn(db_path=str(db_path) if db_path else None)
    if json_only:
        typer.echo(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"removed_docs={res['removed_docs']} removed_chunks={res['removed_chunks']}")

# Entry point
if __name__ == "__main__":  # pragma: no cover
    app()
