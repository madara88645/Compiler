from __future__ import annotations

from app.plugins import PluginContext, PromptcPlugin


def _process_ir(ir, ctx: PluginContext) -> None:
    if "haiku" not in ctx.text.lower():
        return
    constraint = "Ensure the response follows a haiku structure"
    if constraint not in ir.constraints:
        ir.constraints.append(constraint)
    ir.metadata.setdefault("notes", []).append("haiku_plugin")


def get_plugin() -> PromptcPlugin:
    return PromptcPlugin(
        name="SampleHaiku",
        version="0.1.0",
        description="Adds a haiku constraint when prompt mentions haiku",
        process_ir=_process_ir,
    )
