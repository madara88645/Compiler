"""Compile-family commands: `compile` and `batch` (plus the shared `_run_compile`)."""

from __future__ import annotations

import sys
import json
import orjson
import yaml
import time
import typer
from typing import List
from pathlib import Path
from rich import print
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from app.analytics import AnalyticsManager, create_record_from_ir
from cli.render import get_console, render_summary_card, render_prompt_sections

from cli.commands._base import app
from cli.commands._helpers import _write_output

# Constants
HEURISTIC_VERSION = "1.0.0"


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
    system_prompt = emit_system_prompt(ir) if ir else (emit_system_prompt_v2(ir2) if ir2 else "")
    if quiet:
        print(system_prompt)
        return
    user_prompt = emit_user_prompt(ir) if ir else (emit_user_prompt_v2(ir2) if ir2 else "")
    plan = emit_plan(ir) if ir else (emit_plan_v2(ir2) if ir2 else "")
    expanded = (
        emit_expanded_prompt(ir, diagnostics=diagnostics)
        if ir
        else (emit_expanded_prompt_v2(ir2, diagnostics=diagnostics) if ir2 else "")
    )
    if json_only:
        data = ir_json
        fmt_l = (fmt or "json").lower()
        # Prepare payload according to desired format
        if fmt_l in {"yaml", "yml"}:
            if yaml is None:
                typer.secho("PyYAML not installed; falling back to JSON", fg=typer.colors.YELLOW)
                # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
                payload = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
                default_name = "ir.json"
            else:
                payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # type: ignore
                default_name = "ir.yaml"
        else:
            # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
            payload = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
            default_name = "ir.json"
        if out or out_dir:
            if fmt_l == "md" and (ir or ir2):
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
                    + orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
                    + "\n```"
                )
                _write_output("\n".join(md_parts), out, out_dir, default_name="promptc.md")
                return
            _write_output(payload, out, out_dir, default_name=default_name)
            return
        # Print to console
        if fmt_l in {"yaml", "yml"} and yaml is not None:
            typer.echo(payload)
        elif fmt_l == "md" and (ir or ir2):
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
                + orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
                + "\n```"
            )
            typer.echo("\n".join(md_parts))
        else:
            typer.echo(payload)
        return
    # Phase 2: human-first console output is rendered below (after the save branch).
    # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
    rendered = orjson.dumps(ir_json, option=orjson.OPT_INDENT_2).decode("utf-8")
    if out or out_dir:
        fmt_l = (fmt or "json").lower()
        # Support --format md to save prompts as Markdown (v1 or v2 rendering)
        if fmt_l == "md" and (ir or ir2):
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
    console = get_console()
    if ir:
        print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
        print(f"[bold white]Role:[/bold white] {ir.role}")
    else:
        render_summary_card(console, ir_json)
    render_prompt_sections(console, system_prompt, user_prompt, plan, expanded)


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
        False,
        "--render-v2",
        help="Deprecated for compile (IR v2 prompts now render by default); still used by batch --format md.",
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
    summary_json: Path = typer.Option(
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
                        # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
                        line = orjson.dumps(obj).decode("utf-8")
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
                import logging

                logging.getLogger(__name__).error(f"CLI core error: {e}")
                errors.append((src, "An internal error occurred."))
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
            # Bolt Optimization: orjson.dumps is significantly faster than json.dumps for CLI output serialization
            summary_json.write_text(
                orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8"
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
            print(
                f"[done] {len(files)} files -> outputs in {int(elapsed_ms)} ms (avg {avg_ms:.1f} ms) jobs={jobs}"
            )
            if errors:
                for p, msg in errors[:5]:
                    typer.secho(f"[error] {p}: {msg}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    except Exception as e:
        typer.secho(f"Batch processing failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
