"""Render a PR Safety report as GitHub-ready Markdown.

Python port of ``web/app/pr-safety/markdown.ts`` (the source of truth). Pure
formatting of the existing offline report payload — no network calls, no
auto-commenting. The caller copies or downloads the result themselves.
"""

from __future__ import annotations

from app.pr_safety.models import PrSafetyReport, PrSafetyVerdict

VERDICT_LABEL: dict[PrSafetyVerdict, str] = {
    "merge": "MERGE — No blocking safety signals detected",
    "hold": "HOLD — Address the flagged signals before merging",
    "split": "SPLIT — Break this PR into smaller, focused changes",
    "rebase": "REBASE — Update the branch before merging",
}


def report_to_markdown(report: PrSafetyReport) -> str:
    lines: list[str] = []

    lines.append("# PR Safety Report")
    lines.append("")
    lines.append(f"**Verdict:** {VERDICT_LABEL[report.verdict]}")
    if report.title.strip():
        lines.append("")
        lines.append(f"**PR:** {report.title.strip()}")

    # Changed files
    lines.append("")
    lines.append(f"## Changed files ({report.changed_files.total})")
    if not report.changed_files.groups:
        lines.append("")
        lines.append("_No files provided._")
    else:
        for group in report.changed_files.groups:
            lines.append("")
            lines.append(f"### {group.name}")
            for file in group.files:
                lines.append(f"- `{file}`")

    # Risky areas
    lines.append("")
    lines.append(f"## Risky areas (status: {report.risky_areas.status})")
    if not report.risky_areas.hits:
        lines.append("- No risky areas detected")
    else:
        for hit in report.risky_areas.hits:
            lines.append(f"- **{hit.category}** — `{hit.file}`: {hit.reason}")

    # Branch freshness
    lines.append("")
    lines.append(f"## Branch freshness (status: {report.branch_freshness.status})")
    if report.branch_freshness.commits_behind is not None:
        n = report.branch_freshness.commits_behind
        lines.append(f"- {n} commit{'' if n == 1 else 's'} behind base")
    for note in report.branch_freshness.notes:
        lines.append(f"- {note}")

    # Test coverage
    lines.append("")
    lines.append(f"## Test coverage (status: {report.test_coverage.status})")
    if not report.test_coverage.gaps:
        lines.append("- No missing test coverage detected for changed source files")
    else:
        for gap in report.test_coverage.gaps:
            lines.append(f"- `{gap.file}` — {gap.reason}")

    # Scope match
    lines.append("")
    lines.append(f"## Scope match (status: {report.scope_match.status})")
    if not report.scope_match.notes:
        lines.append("- Changed files line up with the PR title and description")
    else:
        for note in report.scope_match.notes:
            lines.append(f"- {note}")

    repo_signals = getattr(report, "repo_signals", None)
    if repo_signals is not None:
        lines.append("")
        lines.append("## Repository signals (advisory)")
        lines.append(f"- Source: {repo_signals.source.replace('_', ' ')}")

        if repo_signals.owners:
            lines.append("")
            lines.append("### Suggested owners")
            for match in repo_signals.owners:
                lines.append(f"- `{match.file}` → {', '.join(match.owners)}")

        if repo_signals.overlapping_workflows:
            lines.append("")
            lines.append("### Overlapping PR workflows")
            for workflow in repo_signals.overlapping_workflows:
                jobs = f"; jobs: {', '.join(workflow.jobs)}" if workflow.jobs else ""
                lines.append(f"- `{workflow.path}` ({workflow.name}){jobs}")

        if repo_signals.detected_commands:
            lines.append("")
            lines.append("### Detected commands")
            for command in repo_signals.detected_commands:
                lines.append(f"- **{command.name}:** `{command.command}` (from `{command.source}`)")

        if repo_signals.stacks:
            lines.append("")
            lines.append("### Detected stacks")
            for stack in repo_signals.stacks:
                frameworks = f" ({', '.join(stack.frameworks)})" if stack.frameworks else ""
                lines.append(f"- {stack.language}{frameworks}")

        if repo_signals.warnings:
            lines.append("")
            lines.append("### Collection warnings")
            for warning in repo_signals.warnings:
                lines.append(f"- {warning}")

        if not any(
            (
                repo_signals.owners,
                repo_signals.overlapping_workflows,
                repo_signals.detected_commands,
                repo_signals.stacks,
                repo_signals.warnings,
            )
        ):
            lines.append("- No repository-specific signals detected")

    # Recommendations
    lines.append("")
    lines.append("## Recommendations")
    if not report.recommendations:
        lines.append("- None")
    else:
        for rec in report.recommendations:
            lines.append(f"- {rec}")

    lines.append("")
    lines.append("---")
    lines.append(
        "_Generated by Compiler PR Safety — offline heuristic advisory, not merge blocking._"
    )

    return "\n".join(lines) + "\n"
