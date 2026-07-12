from app.adapters.agent_ir import (
    _infer_hook_suggestions,
    _infer_mcp_servers,
    _infer_ci_automation_intent,
    _infer_memory_outline,
)


def test_infer_hook_suggestions_baseline_only():
    suggestions = _infer_hook_suggestions("a simple backend service")
    assert suggestions == [
        "Block reads of .env and secrets before tool execution.",
        "Run targeted tests or lint checks after code edits.",
    ]


def test_infer_hook_suggestions_frontend_keyword():
    suggestions = _infer_hook_suggestions("react frontend dashboard")
    assert "Run frontend lint/build hooks after editing TSX or CSS." in suggestions


def test_infer_hook_suggestions_deploy_keyword():
    suggestions = _infer_hook_suggestions("automate the ci deploy pipeline")
    assert "Require human confirmation before git push or deploy commands." in suggestions


def test_infer_hook_suggestions_both_keywords():
    suggestions = _infer_hook_suggestions("react ui with ci release automation")
    assert len(suggestions) == 4


def test_infer_mcp_servers_matches_known_keywords():
    assert _infer_mcp_servers("integrates with github and slack") == ["github", "slack"]


def test_infer_mcp_servers_no_match():
    assert _infer_mcp_servers("a plain text agent") == []


def test_infer_mcp_servers_preserves_mapping_order():
    assert _infer_mcp_servers("notion figma sentry jira") == ["figma", "notion", "jira", "sentry"]


def test_infer_ci_automation_intent_review():
    assert _infer_ci_automation_intent("review every pull request") == ["review"]


def test_infer_ci_automation_intent_all_categories():
    text = "review pr, implement feature, autofix flaky bug"
    assert _infer_ci_automation_intent(text) == ["review", "implementation", "autofix"]


def test_infer_ci_automation_intent_no_match():
    assert _infer_ci_automation_intent("a passive summary tool") == []


def test_infer_memory_outline_minimal():
    outline = _infer_memory_outline(name="Agent", role="", goals=[], constraints=[])
    assert outline == ["Agent name: Agent"]


def test_infer_memory_outline_truncates_goals_and_constraints_to_three():
    outline = _infer_memory_outline(
        name="Agent",
        role="Reviewer",
        goals=["g1", "g2", "g3", "g4"],
        constraints=["c1", "c2", "c3", "c4"],
    )
    assert outline == [
        "Agent name: Agent",
        "Primary role: Reviewer",
        "Goal: g1",
        "Goal: g2",
        "Goal: g3",
        "Constraint: c1",
        "Constraint: c2",
        "Constraint: c3",
    ]
