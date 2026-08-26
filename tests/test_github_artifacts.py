import pytest

from app.github_artifacts import render_github_artifact, render_artifact_chain
from app.models_v2 import IRv2, PolicyV2


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_issue_brief_renders_intent_and_policy_sections():
    artifact = render_github_artifact(
        "issue-brief",
        "Analyze my stock portfolio allocation and outline the safest next steps.",
    )

    assert "# Issue Brief" in artifact
    assert "## Intent" in artifact
    assert "## Policy" in artifact
    assert "Risk Level: high" in artifact
    assert "Execution Mode: human_approval_required" in artifact


def test_pr_review_brief_is_deterministic_for_policy_and_checkpoints():
    artifact = render_github_artifact(
        "pr-review-brief",
        "Debug this Python traceback from my repository and inspect logs in C:\\app\\logs.",
    )

    assert "# PR Review Brief" in artifact
    assert "workspace_read" in artifact
    assert "path_must_stay_within_workspace" in artifact
    assert "## Review Focus" in artifact


# ---------------------------------------------------------------------------
# Realistic scenario tests — issue brief
# ---------------------------------------------------------------------------


def test_issue_brief_from_rate_limiting_request():
    """Real-world issue: add rate limiting to an API endpoint."""
    artifact = render_github_artifact(
        "issue-brief",
        (
            "Our /compile endpoint is getting hammered by bots. "
            "Add per-IP rate limiting with a 60 req/min threshold. "
            "Return 429 with Retry-After header when exceeded."
        ),
    )

    assert "# Issue Brief" in artifact
    assert "## Goals" in artifact
    # Should detect intents related to the request
    assert "## Intent" in artifact
    assert "## Policy" in artifact
    # Should produce a non-empty Goals section
    lines = artifact.split("\n")
    goals_idx = next(i for i, line in enumerate(lines) if "## Goals" in line)
    # At least one bullet under Goals
    assert any(line.startswith("- ") for line in lines[goals_idx + 1 : goals_idx + 5])


def test_issue_brief_low_risk_documentation_request():
    """Low-risk issue: improve README documentation."""
    artifact = render_github_artifact(
        "issue-brief",
        "Update the README to include a quickstart guide and installation instructions.",
    )

    assert "# Issue Brief" in artifact
    assert "Risk Level: low" in artifact
    assert "auto_ok" in artifact


# ---------------------------------------------------------------------------
# Realistic scenario tests — implementation checklist
# ---------------------------------------------------------------------------


def test_implementation_checklist_has_checkbox_items():
    """Checklist should produce markdown checkboxes."""
    artifact = render_github_artifact(
        "implementation-checklist",
        (
            "Build a file upload feature: accept PDF and TXT files up to 10MB, "
            "chunk them into 512-token segments, embed with a local model, "
            "store in SQLite vector store, and show upload progress in the UI."
        ),
    )

    assert "# Implementation Checklist" in artifact
    assert "## Checklist" in artifact
    # Must have at least 1 checkbox item (heuristic step count depends on input)
    checkbox_count = artifact.count("- [ ]")
    assert checkbox_count >= 1, f"Expected >=1 checkboxes, got {checkbox_count}"


def test_implementation_checklist_sensitive_domain():
    """Healthcare spec should trigger high risk + human approval."""
    artifact = render_github_artifact(
        "implementation-checklist",
        (
            "Create a patient intake form that collects name, date of birth, "
            "insurance ID, and medical history. Store data encrypted at rest "
            "and ensure HIPAA compliance for all API endpoints."
        ),
    )

    assert "# Implementation Checklist" in artifact
    assert "Risk Level: high" in artifact
    assert "human_approval_required" in artifact


# ---------------------------------------------------------------------------
# Realistic scenario tests — PR review brief
# ---------------------------------------------------------------------------


def test_pr_review_brief_from_feature_pr():
    """PR review brief for a typical feature PR."""
    artifact = render_github_artifact(
        "pr-review-brief",
        (
            "This PR adds a caching layer to the compile pipeline. "
            "Identical prompts return cached IR within 50ms instead of "
            "re-running the full heuristic chain. Cache is LRU with "
            "128 entries and 5-minute TTL. Includes 8 new tests."
        ),
    )

    assert "# PR Review Brief" in artifact
    assert "## Review Focus" in artifact
    assert "## Policy" in artifact
    # Review Focus should have at least one bullet
    lines = artifact.split("\n")
    focus_idx = next(i for i, line in enumerate(lines) if "## Review Focus" in line)
    assert any(line.startswith("- ") for line in lines[focus_idx + 1 : focus_idx + 8])


# ---------------------------------------------------------------------------
# Edge cases and structural assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    ["issue-brief", "implementation-checklist", "pr-review-brief", "workflow-brief"],
)
def test_all_artifact_types_produce_valid_markdown(kind):
    """Every artifact type should start with an H1 and end with a newline."""
    artifact = render_github_artifact(kind, "Write unit tests for the auth module.")

    assert artifact.startswith("# ")
    assert artifact.endswith("\n")
    # Must contain both Intent and Policy sections
    assert "## Intent" in artifact
    assert "## Policy" in artifact


@pytest.mark.parametrize(
    "kind",
    ["issue-brief", "implementation-checklist", "pr-review-brief"],
)
def test_artifact_policy_fields_always_present(kind):
    """Policy section must always include risk level, execution mode, data sensitivity."""
    artifact = render_github_artifact(
        kind,
        "Refactor the token counting utility to use a singleton encoder pattern.",
    )

    assert "Risk Level:" in artifact
    assert "Execution Mode:" in artifact
    assert "Data Sensitivity:" in artifact


# ---------------------------------------------------------------------------
# New: workflow-brief, artifact chain, enforcement checklist
# ---------------------------------------------------------------------------


def test_workflow_brief_contains_all_sections():
    """Composite workflow-brief should contain Goals, Checklist, and Review Focus."""
    artifact = render_github_artifact(
        "workflow-brief",
        (
            "Build a file upload feature: accept PDF and TXT files up to 10MB, "
            "chunk them into 512-token segments, embed with a local model, "
            "store in SQLite vector store, and show upload progress in the UI."
        ),
    )

    assert "# Workflow Brief" in artifact
    assert "## Intent" in artifact
    assert "## Policy" in artifact
    assert "## Goals" in artifact
    assert "## Checklist" in artifact
    assert "## Review Focus" in artifact
    assert artifact.startswith("# ")
    assert artifact.endswith("\n")


def test_artifact_chain_renders_three_linked_sections():
    """Artifact chain should produce 3 artifacts separated by --- with cross-references."""
    chain = render_artifact_chain("Write unit tests for the auth module.")

    assert "# Issue Brief" in chain
    assert "# Implementation Checklist" in chain
    assert "# PR Review Brief" in chain
    assert "---" in chain
    assert "See also:" in chain


def test_enforcement_checklist_for_high_risk():
    """Financial prompt should produce enforcement checklist with GATE."""
    artifact = render_github_artifact(
        "issue-brief",
        "Analyze my stock portfolio allocation and suggest an investment strategy.",
    )

    assert "## Enforcement Checklist" in artifact
    assert "**GATE:** Human review required before merge/deploy" in artifact
    assert "- [ ]" in artifact


def test_enforcement_checklist_absent_for_low_risk():
    """Benign prompt should not have an enforcement checklist."""
    artifact = render_github_artifact(
        "issue-brief",
        "Explain the difference between TCP and UDP protocols.",
    )

    assert "## Enforcement Checklist" not in artifact


# ---------------------------------------------------------------------------
# New: _render_enforcement_checklist() edge cases
# ---------------------------------------------------------------------------


def test_enforcement_checklist_high_risk_no_sanitization_rules_shows_only_gate():
    # risk_level="high" with sanitization_rules=[] still enters the checklist branch
    # (condition: not sanitization_rules AND risk_level != "high" — the second part
    # is False, so the early-return guard does not fire). Only the GATE line is added.
    ir2 = IRv2(goals=["Deploy"], policy=PolicyV2(risk_level="high", sanitization_rules=[]))
    artifact = render_github_artifact("issue-brief", "Deploy the service.", ir2=ir2)

    assert "## Enforcement Checklist" in artifact
    assert "**GATE:** Human review required before merge/deploy" in artifact
    checklist_lines = [line for line in artifact.splitlines() if line.startswith("- [ ]")]
    assert len(checklist_lines) == 1, (
        f"Expected exactly 1 checklist item (GATE only), got: {checklist_lines}"
    )


def test_enforcement_checklist_unknown_rule_uses_fallback_label():
    # Rules absent from _RULE_ACTIONS render as "Enforce {rule} policy" via .get() fallback.
    ir2 = IRv2(
        goals=["Comply"],
        policy=PolicyV2(
            risk_level="medium",
            sanitization_rules=["custom_compliance_check"],
        ),
    )
    artifact = render_github_artifact("issue-brief", "Ensure compliance.", ir2=ir2)

    assert "## Enforcement Checklist" in artifact
    assert "- [ ] Enforce custom_compliance_check policy" in artifact


def test_issue_brief_empty_goals_falls_back_to_raw_text():
    # When goals=[], tasks=[], steps=[], the issue-brief Goals section
    # falls back to [text] via `ir2.goals or [text]`.
    ir2 = IRv2(goals=[], tasks=[], steps=[])
    raw_text = "No goals or tasks available."
    artifact = render_github_artifact("issue-brief", raw_text, ir2=ir2)

    assert "## Goals" in artifact
    assert raw_text in artifact
