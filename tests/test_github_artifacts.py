from app.github_artifacts import render_github_artifact


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
