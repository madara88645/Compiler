from __future__ import annotations

from typing import Literal

from app.compiler import compile_text_v2


ArtifactType = Literal["issue-brief", "implementation-checklist", "pr-review-brief"]


def render_github_artifact(kind: ArtifactType, text: str) -> str:
    ir2 = compile_text_v2(text, offline_only=True)
    title = {
        "issue-brief": "Issue Brief",
        "implementation-checklist": "Implementation Checklist",
        "pr-review-brief": "PR Review Brief",
    }[kind]

    lines = [
        f"# {title}",
        "",
        "## Intent",
        f"- Domain: {ir2.domain}",
        f"- Persona: {ir2.persona}",
        f"- Intents: {', '.join(ir2.intents) if ir2.intents else 'general'}",
        "",
        "## Policy",
        f"- Risk Level: {ir2.policy.risk_level}",
        f"- Risk Domains: {', '.join(ir2.policy.risk_domains) if ir2.policy.risk_domains else 'none'}",
        f"- Execution Mode: {ir2.policy.execution_mode}",
        f"- Data Sensitivity: {ir2.policy.data_sensitivity}",
    ]

    if ir2.policy.allowed_tools:
        lines.append(f"- Allowed Tools: {', '.join(ir2.policy.allowed_tools)}")
    if ir2.policy.forbidden_tools:
        lines.append(f"- Forbidden Tools: {', '.join(ir2.policy.forbidden_tools)}")
    if ir2.policy.sanitization_rules:
        lines.append(f"- Sanitization Rules: {', '.join(ir2.policy.sanitization_rules)}")

    if kind == "issue-brief":
        lines.extend(_section("Goals", ir2.goals or [text]))
        lines.extend(_section("Tasks", ir2.tasks or ir2.goals or [text]))
    elif kind == "implementation-checklist":
        steps = [step.text for step in ir2.steps] or ir2.tasks or ir2.goals or [text]
        lines.extend(["", "## Checklist", *[f"- [ ] {step}" for step in steps]])
    elif kind == "pr-review-brief":
        review_focus = ir2.constraints[:4] or ir2.tasks[:4] or ir2.goals[:4]
        lines.extend(
            _section(
                "Review Focus",
                [item.text if hasattr(item, "text") else item for item in review_focus],
            )
        )

    return "\n".join(lines).strip() + "\n"


def _section(title: str, items: list[str]) -> list[str]:
    return ["", f"## {title}", *[f"- {item}" for item in items if item]]
