"""Offline `compile-export` command."""

from __future__ import annotations

from pathlib import Path

import orjson
import typer

from app.compile_export import render_compile_export
from app.compiler import compile_text_v2
from app.emitters import (
    emit_expanded_prompt_v2,
    emit_plan_v2,
    emit_system_prompt_v2,
    emit_user_prompt_v2,
)
from app.readiness.analyzer import analyze_readiness
from app.readiness.markdown import report_to_markdown
from cli.commands._base import app
from cli.commands._helpers import _write_output


@app.command("compile-export")
def compile_export_cmd(
    text: str = typer.Argument(..., help="Prompt text to compile and export"),
    out_dir: Path | None = typer.Option(
        None,
        "--out-dir",
        help="Write compile-export.md and compile-export.json to this directory",
    ),
) -> None:
    """Compile a prompt offline and export executable Markdown plus structured JSON."""
    ir = compile_text_v2(text, enable_context_retrieval=False)
    system_prompt = emit_system_prompt_v2(ir)
    user_prompt = emit_user_prompt_v2(ir)
    plan = emit_plan_v2(ir)
    readiness_report = analyze_readiness(text, ir)
    readiness_markdown = report_to_markdown(readiness_report)

    data = {
        "ir": ir.model_dump(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "plan": plan,
        "expanded_prompt": emit_expanded_prompt_v2(ir),
        "readiness": readiness_report.model_dump(),
        "readiness_markdown": readiness_markdown,
    }
    markdown = render_compile_export(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        plan=plan,
        readiness_markdown=readiness_markdown,
    )

    if out_dir is None:
        typer.echo(markdown)
        return

    _write_output(markdown, None, out_dir, default_name="compile-export.md")
    json_output = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
    _write_output(json_output, None, out_dir, default_name="compile-export.json")
