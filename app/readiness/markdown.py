from __future__ import annotations

from app.readiness.models import ReadinessReport

_VERDICT_TITLE = {
    "ready": "Ready to compile",
    "clarify": "Clarify before compiling",
    "risky": "Risky — review first",
    "noise": "Not a real task",
}


def report_to_markdown(report: ReadinessReport) -> str:
    lines = [f"## Readiness: {report.verdict} — {_VERDICT_TITLE[report.verdict]}", ""]
    if report.signals:
        lines.append("### Signals")
        for sig in report.signals:
            lines.append(f"- **{sig.kind}**: {sig.message}")
        lines.append("")
    if report.questions:
        lines.append("### Clarify first")
        for q in report.questions:
            lines.append(f"- {q}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
