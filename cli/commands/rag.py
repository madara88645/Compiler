
import typer
from typing import List, Optional
from pathlib import Path
import json
import yaml
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

app = typer.Typer(help="Lightweight local RAG (SQLite FTS5)")

def _write_output(content: str, out: Optional[Path], out_dir: Optional[Path], default_name: str):
    """Refactored helper for output writing (duplicated for now or shared later)."""
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {out}")
    elif out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / default_name
        path.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {path}")
    else:
        typer.echo(content)

@app.command("index")
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

@app.command("query")
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

@app.command("pack")
def rag_pack(
    query: List[str] = typer.Argument(..., help="Query text"),
    k: int = typer.Option(5, "--k", help="Top-K results"),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    max_chars: int = typer.Option(4000, "--max-chars", help="Context window budget"),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Approximate token budget"),
    token_ratio: float = typer.Option(4.0, "--token-ratio", help="Chars per token est"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format: md|yaml|json"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
    dedup: bool = typer.Option(False, "--dedup", help="De-duplicate chunks"),
    token_aware: bool = typer.Option(False, "--token-aware", help="Enable token-aware packing"),
):
    q = " ".join(query)
    # Basic search for packing (default fts)
    res = search(q, k=k, db_path=str(db_path) if db_path else None)
    packed = pack_context(
        q,
        res,
        max_chars=max_chars,
        max_tokens=max_tokens,
        token_chars=token_ratio,
        dedup=dedup,
        token_aware=token_aware,
    )
    fmt_l = (format or "json").lower() if format else None
    if json_out or fmt_l or out or out_dir:
        if fmt_l == "md":
            payload = packed["packed"]
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
        typer.echo(packed["packed"])

@app.command("stats")
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

@app.command("prune")
def rag_prune(
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite DB path"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON output"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Output format: yaml|json (default json)"
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Write output to file"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Write output into directory"),
):
    # Legacy prune didn't expose 'days' in CLI, or defaulted?
    # Using rag_prune_fn without days to match main_legacy.py
    # If rag_prune_fn requires days, then legacy code relied on default?
    # Inspecting rag_prune_fn signature would be good, but following legacy code exactly.
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
