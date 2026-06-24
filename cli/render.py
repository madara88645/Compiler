"""CLI presentation helpers (human-tier output only).

IMPORTANT: machine-output paths (--json-only / --out / --format / --quiet /
batch) must NOT use these helpers — they must emit plain, unstyled payloads so
piping and golden-file tests stay stable.
"""
from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

SECTION_TITLES = {
    "system": "System Prompt",
    "user": "User Prompt",
    "plan": "Plan",
    "expanded": "Expanded Prompt",
}


def get_console() -> Console:
    """Return a Console for human CLI output."""
    return Console()


def render_summary_card(console: Console, ir_json: dict) -> None:
    """Print a compact summary panel from an IR v2 dict (model_dump())."""
    policy = (ir_json.get("metadata") or {}).get("policy_summary") or {}
    rows = [
        ("Persona", str(ir_json.get("persona") or "—")),
        ("Domain", str(ir_json.get("domain") or "—")),
        ("Risk", str(policy.get("risk_level") or "—")),
        ("Output", str(ir_json.get("output_format") or "—")),
        ("Goals", str(len(ir_json.get("goals") or []))),
        ("Constraints", str(len(ir_json.get("constraints") or []))),
    ]
    body = "\n".join(f"{escape(k)}: {escape(v)}" for k, v in rows)
    console.print(Panel(body, title="Summary", expand=False))


def render_prompt_sections(
    console: Console, system: str, user: str, plan: str, expanded: str
) -> None:
    """Print each non-empty prompt section under a rule, markup-safe."""
    sections = [
        (SECTION_TITLES["system"], system),
        (SECTION_TITLES["user"], user),
        (SECTION_TITLES["plan"], plan),
        (SECTION_TITLES["expanded"], expanded),
    ]
    for title, text in sections:
        if text:
            console.rule(title)
            console.print(text, markup=False)
