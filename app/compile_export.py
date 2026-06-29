"""Shared rendering for compile export documents."""

from __future__ import annotations


def render_compile_export(
    *,
    system_prompt: str,
    user_prompt: str,
    plan: str,
    readiness_markdown: str,
) -> str:
    """Render a self-contained Markdown document from compiled prompt fields."""
    return (
        "# Prompt Compiler Export\n\n"
        f"## System Prompt\n\n{system_prompt.strip()}\n\n"
        f"## User Prompt\n\n{user_prompt.strip()}\n\n"
        f"## Plan\n\n{plan.strip()}\n\n"
        f"{readiness_markdown.rstrip()}\n"
    )
