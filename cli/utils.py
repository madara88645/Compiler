from __future__ import annotations
import sys
import json
import time
from pathlib import Path
import typer
from rich import print

# Optional YAML support
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

from app.compiler import (
    compile_text,
    compile_text_v2,
    optimize_ir,
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
from app.validator import validate_prompt
from app.analytics import AnalyticsManager, create_record_from_ir


def _write_output(
    content: str, out: Path | None, out_dir: Path | None, default_name: str = "output.txt"
):
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"✓ Saved to {out}")
    elif out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / default_name
        p.write_text(content, encoding="utf-8")
        print(f"✓ Saved to {p}")
    else:
        # Default to stdout
        print(content)


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
        ir = None

    if persona and (ir is not None):
        ir.persona = persona.strip().lower()

    ir_json = ir.model_dump() if ir else ir2.model_dump()
    if trace and ir:
        ir_json["trace"] = generate_trace(ir)

    validation_result = None
    if validate:
        if ir2 is None:
            print("[warn] Validation skipped (IR v1)", file=sys.stderr)
        else:
            try:
                validation_result = validate_prompt(ir2, full_text)
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
            pass

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
                payload = "".join(md_parts)
                default_name = "prompt.md"
            _write_output(payload, out, out_dir, default_name)
        else:
            print(payload)
    else:
        # Standard rich output
        from rich.panel import Panel
        from rich.syntax import Syntax

        console = typer.main.get_console()  # type: ignore

        if system_prompt:
            console.print(
                Panel(Syntax(system_prompt, "markdown"), title="System Prompt", border_style="blue")
            )
        if user_prompt:
            console.print(
                Panel(Syntax(user_prompt, "markdown"), title="User Prompt", border_style="green")
            )
        if plan:
            console.print(Panel(plan, title="Plan", border_style="yellow"))
        if expanded:
            console.print(
                Panel(Syntax(expanded, "markdown"), title="Expanded", border_style="magenta")
            )

        if out or out_dir:
            _write_output(expanded, out, out_dir, "expanded.txt")
