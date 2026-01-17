from __future__ import annotations


def _render_prompt_pack_md(
    system_prompt: str,
    user_prompt: str,
    plan: str,
    expanded: str,
    title: str = "Prompt Pack",
) -> str:
    """Render a prompt pack in Markdown format."""
    parts = [f"# {title}"]
    if system_prompt:
        parts.append(f"\n\n## System Prompt\n\n{system_prompt}")
    if user_prompt:
        parts.append(f"\n\n## User Prompt\n\n{user_prompt}")
    if plan:
        parts.append(f"\n\n## Plan\n\n{plan}")
    if expanded:
        parts.append(f"\n\n## Expanded Prompt\n\n{expanded}")
    return "".join(parts).strip()


def _render_prompt_pack_txt(system_prompt: str, user_prompt: str, plan: str, expanded: str) -> str:
    """Render a prompt pack in Plain Text format."""
    parts = []
    if system_prompt:
        parts.append(f"--- System Prompt ---\n{system_prompt}")
    if user_prompt:
        parts.append(f"\n\n--- User Prompt ---\n{user_prompt}")
    if plan:
        parts.append(f"\n\n--- Plan ---\n{plan}")
    if expanded:
        parts.append(f"\n\n--- Expanded Prompt ---\n{expanded}")
    return "".join(parts).strip()
