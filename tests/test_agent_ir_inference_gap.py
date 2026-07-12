"""Direct unit coverage for app.adapters.agent_ir keyword-inference helpers.

These pure functions seed the tool permissions, MCP servers, hook
suggestions, CI automation intent, and CLAUDE.md memory outline written into
generated agent-pack exports. They take already-lowercased combined text
(see `_build_ir`'s `combined_text = "...".lower()`) and are otherwise
untested in isolation — a bug here silently over- or under-grants tool
access in exported agent packs.
"""

from app.adapters.agent_ir import (
    _infer_allowed_tools,
    _infer_ci_automation_intent,
    _infer_hook_suggestions,
    _infer_mcp_servers,
    _infer_memory_outline,
)


class TestInferAllowedTools:
    def test_base_tools_always_present(self) -> None:
        tools = _infer_allowed_tools("a generic assistant with no special needs")
        assert {"Read", "Edit", "Write", "Glob", "Grep"}.issubset(set(tools))
        assert "Bash" not in tools
        assert "WebSearch" not in tools

    def test_code_keyword_adds_bash(self) -> None:
        tools = _infer_allowed_tools("helps debug python code")
        assert "Bash" in tools

    def test_research_keyword_adds_web_tools(self) -> None:
        tools = _infer_allowed_tools("does web research and cites sources")
        assert "WebSearch" in tools
        assert "WebFetch" in tools

    def test_github_keyword_adds_bash(self) -> None:
        tools = _infer_allowed_tools("reviews github pull request diffs")
        assert "Bash" in tools

    def test_result_is_sorted_and_deduped(self) -> None:
        tools = _infer_allowed_tools("code code code react react")
        assert tools == sorted(set(tools))


class TestInferHookSuggestions:
    def test_default_suggestions_always_present(self) -> None:
        suggestions = _infer_hook_suggestions("a plain assistant")
        assert len(suggestions) == 2
        assert any("secrets" in s for s in suggestions)

    def test_frontend_keyword_adds_lint_hook(self) -> None:
        suggestions = _infer_hook_suggestions("builds react ui components")
        assert any("frontend lint" in s.lower() for s in suggestions)

    def test_deploy_keyword_adds_confirmation_hook(self) -> None:
        suggestions = _infer_hook_suggestions("handles ci deploy pipelines")
        assert any("confirmation" in s.lower() for s in suggestions)

    def test_no_extra_keywords_yields_only_defaults(self) -> None:
        assert len(_infer_hook_suggestions("writes poetry")) == 2


class TestInferMcpServers:
    def test_no_keywords_returns_empty(self) -> None:
        assert _infer_mcp_servers("a general assistant") == []

    def test_single_keyword_maps_to_server(self) -> None:
        assert _infer_mcp_servers("posts updates to slack") == ["slack"]

    def test_multiple_keywords_preserve_mapping_order(self) -> None:
        result = _infer_mcp_servers("tracks github issues and jira tickets")
        assert result == ["github", "jira"]

    def test_unmatched_keyword_is_ignored(self) -> None:
        assert _infer_mcp_servers("uses linear and trello") == []


class TestInferCiAutomationIntent:
    def test_no_keywords_returns_empty(self) -> None:
        assert _infer_ci_automation_intent("writes documentation") == []

    def test_review_keyword(self) -> None:
        assert _infer_ci_automation_intent("reviews every pull request") == ["review"]

    def test_implementation_keyword(self) -> None:
        assert _infer_ci_automation_intent("implements the requested feature") == ["implementation"]

    def test_autofix_keyword(self) -> None:
        assert _infer_ci_automation_intent("fix failing test automatically") == ["autofix"]

    def test_all_three_intents_combine_in_order(self) -> None:
        text = "review pull requests, implement new features, and autofix flaky tests"
        assert _infer_ci_automation_intent(text) == [
            "review",
            "implementation",
            "autofix",
        ]


class TestInferMemoryOutline:
    def test_name_only(self) -> None:
        outline = _infer_memory_outline(name="Reviewer", role="", goals=[], constraints=[])
        assert outline == ["Agent name: Reviewer"]

    def test_role_is_included_when_present(self) -> None:
        outline = _infer_memory_outline(
            name="Reviewer", role="Code reviewer", goals=[], constraints=[]
        )
        assert "Primary role: Code reviewer" in outline

    def test_goals_and_constraints_are_capped_at_three(self) -> None:
        goals = [f"goal-{i}" for i in range(5)]
        constraints = [f"constraint-{i}" for i in range(5)]
        outline = _infer_memory_outline(name="A", role="", goals=goals, constraints=constraints)
        goal_lines = [line for line in outline if line.startswith("Goal:")]
        constraint_lines = [line for line in outline if line.startswith("Constraint:")]
        assert goal_lines == ["Goal: goal-0", "Goal: goal-1", "Goal: goal-2"]
        assert constraint_lines == [
            "Constraint: constraint-0",
            "Constraint: constraint-1",
            "Constraint: constraint-2",
        ]

    def test_empty_goals_and_constraints_produce_no_extra_lines(self) -> None:
        outline = _infer_memory_outline(name="A", role="", goals=[], constraints=[])
        assert outline == ["Agent name: A"]
