from __future__ import annotations

from typing import Literal

from app.compiler import compile_text_v2
from app.models_v2 import IRv2


ArtifactType = Literal[
    "issue-brief", "implementation-checklist", "pr-review-brief", "workflow-brief"
]

_RULE_ACTIONS = {
    "mask_secrets": "Verify no secrets/credentials in output",
    "mask_sensitive_values": "Confirm PII is masked or redacted",
    "path_must_stay_within_workspace": "Validate all file paths stay within workspace",
    "audit_trail": "Ensure audit logging is enabled",
    "hipaa_filter": "Verify HIPAA-compliant data handling",
    "dry_run_required": "Confirm dry-run mode for infrastructure changes",
    "consent_check": "Verify data consent requirements are met",
}


def render_github_artifact(kind: ArtifactType, text: str, *, ir2: IRv2 | None = None) -> str:
    if ir2 is None:
        ir2 = compile_text_v2(text, offline_only=True)

    if kind == "workflow-brief":
        return _render_workflow_brief(ir2, text)

    title = {
        "issue-brief": "Issue Brief",
        "implementation-checklist": "Implementation Checklist",
        "pr-review-brief": "PR Review Brief",
    }[kind]

    lines = _render_header(ir2, title)
    lines.extend(_render_enforcement_checklist(ir2))

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


def render_artifact_chain(text: str) -> str:
    """Render issue-brief -> implementation-checklist -> pr-review-brief as a linked chain."""
    ir2 = compile_text_v2(text, offline_only=True)

    parts = []
    for kind, see_also in [
        ("issue-brief", ["Implementation Checklist", "PR Review Brief"]),
        ("implementation-checklist", ["Issue Brief", "PR Review Brief"]),
        ("pr-review-brief", ["Issue Brief", "Implementation Checklist"]),
    ]:
        artifact = render_github_artifact(kind, text, ir2=ir2)
        refs = ", ".join(f"[{s}](#{s.lower().replace(' ', '-')})" for s in see_also)
        artifact = artifact.rstrip("\n") + f"\n\n> See also: {refs}\n"
        parts.append(artifact)

    return "\n---\n\n".join(parts)


def _render_workflow_brief(ir2: IRv2, text: str) -> str:
    """Composite artifact combining goals, checklist, review focus, and enforcement."""
    lines = _render_header(ir2, "Workflow Brief")
    lines.extend(_render_enforcement_checklist(ir2))

    # Goals (from issue-brief)
    lines.extend(_section("Goals", ir2.goals or [text]))

    # Checklist (from implementation-checklist)
    steps = [step.text for step in ir2.steps] or ir2.tasks or ir2.goals or [text]
    lines.extend(["", "## Checklist", *[f"- [ ] {step}" for step in steps]])

    # Review Focus (from pr-review-brief)
    review_focus = ir2.constraints[:4] or ir2.tasks[:4] or ir2.goals[:4]
    lines.extend(
        _section(
            "Review Focus",
            [item.text if hasattr(item, "text") else item for item in review_focus],
        )
    )

    return "\n".join(lines).strip() + "\n"


def _render_header(ir2: IRv2, title: str) -> list[str]:
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

    return lines


def _render_enforcement_checklist(ir2: IRv2) -> list[str]:
    if not ir2.policy.sanitization_rules and ir2.policy.risk_level != "high":
        return []

    lines = ["", "## Enforcement Checklist"]
    for rule in ir2.policy.sanitization_rules:
        action = _RULE_ACTIONS.get(rule, f"Enforce {rule} policy")
        lines.append(f"- [ ] {action}")

    if ir2.policy.risk_level == "high":
        lines.append("- [ ] **GATE:** Human review required before merge/deploy")

    return lines


def _section(title: str, items: list[str]) -> list[str]:
    return ["", f"## {title}", *[f"- {item}" for item in items if item]]
