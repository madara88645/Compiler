import pytest

from app.github_artifacts import render_github_artifact


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
    assert "advice_only" in artifact


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
    ["issue-brief", "implementation-checklist", "pr-review-brief"],
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
