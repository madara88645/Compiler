"""CLI presentation helpers (human-tier output only).

IMPORTANT: machine-output paths (--json-only / --out / --format / --quiet /
batch) must NOT use these helpers — they must emit plain, unstyled payloads so
piping and golden-file tests stay stable.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

if TYPE_CHECKING:
    from app.pr_safety.models import PrSafetyReport

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


_VERDICT_LABEL = {
    "merge": "MERGE — No blocking safety signals detected",
    "hold": "HOLD — Address the flagged signals before merging",
    "split": "SPLIT — Break this PR into smaller, focused changes",
    "rebase": "REBASE — Update the branch before merging",
}


def render_pr_safety_report(console: Console, report: PrSafetyReport) -> None:
    """Print a human-tier PR Safety report (verdict panel + ruled sections).

    Human output only — markup-safe via ``rich.markup.escape``. Machine
    formats (json/md) must not route through here (Phase 2 rule).
    """
    verdict = report.verdict
    summary_lines = [
        f"Verdict: {escape(_VERDICT_LABEL.get(verdict, verdict))}",
    ]
    if report.title.strip():
        summary_lines.append(f"PR: {escape(report.title.strip())}")
    summary_lines.append("")
    summary_lines.append(
        "Signals: "
        + "  ".join(
            [
                f"risky={escape(report.risky_areas.status)}",
                f"tests={escape(report.test_coverage.status)}",
                f"branch={escape(report.branch_freshness.status)}",
                f"scope={escape(report.scope_match.status)}",
            ]
        )
    )
    console.print(Panel("\n".join(summary_lines), title="PR Safety", expand=False))

    console.rule(f"Changed files ({report.changed_files.total})")
    if not report.changed_files.groups:
        console.print("No files provided.", markup=False)
    else:
        for group in report.changed_files.groups:
            console.print(f"[bold]{escape(group.name)}[/bold]")
            for file in group.files:
                console.print(f"  {escape(file)}", markup=False)

    console.rule(f"Risky areas (status: {report.risky_areas.status})")
    if not report.risky_areas.hits:
        console.print("No risky areas detected", markup=False)
    else:
        for hit in report.risky_areas.hits:
            label = escape(f"[{hit.category}]")
            console.print(f"  {label} {escape(hit.file)}: {escape(hit.reason)}")

    console.rule(f"Test coverage (status: {report.test_coverage.status})")
    if not report.test_coverage.gaps:
        console.print("No missing test coverage detected for changed source files", markup=False)
    else:
        for gap in report.test_coverage.gaps:
            console.print(f"  {escape(gap.file)}: {escape(gap.reason)}")

    console.rule(f"Branch freshness (status: {report.branch_freshness.status})")
    for note in report.branch_freshness.notes:
        console.print(f"  {escape(note)}")

    console.rule(f"Scope match (status: {report.scope_match.status})")
    if not report.scope_match.notes:
        console.print("Changed files line up with the PR title and description", markup=False)
    else:
        for note in report.scope_match.notes:
            console.print(f"  {escape(note)}")

    console.rule("Recommendations")
    if not report.recommendations:
        console.print("None", markup=False)
    else:
        for rec in report.recommendations:
            console.print(f"  - {escape(rec)}")
