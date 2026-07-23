"""
tests/test_claude_code_adapter_content.py — Direct content coverage for the
pure string/dict formatting helpers in app/adapters/claude_code.py.

These helpers were previously only exercised indirectly through
test_export_adapters.py's path-existence / substring assertions on the full
pack output (e.g. "hooks" not in json.loads(...), "figma" in readme). This
file asserts the actual generated content — including the project's
explicit "no leaked secrets, OpenRouter-only, no end-user API-key prompts"
policy for generated Claude Code packs.
"""

from __future__ import annotations

import json

import yaml

from app.adapters.agent_ir import AgentExportIR
from app.adapters.claude_code import (
    _github_action_workflow,
    _mcp_integration_notes,
    _ordered_tools,
    _pr_reviewer_memory,
    _pr_reviewer_readme,
    _project_settings_json,
    _skill_implementation_markdown,
    _skill_params_markdown,
    _skill_safety_markdown,
)
from app.adapters.skill_ir import SkillExportIR, SkillParam


# ---------------------------------------------------------------------------
# _github_action_workflow
# ---------------------------------------------------------------------------


def test_github_action_workflow_default_is_valid_yaml_with_placeholder_defaults():
    workflow = _github_action_workflow(None)
    parsed = yaml.safe_load(workflow)
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1 quirk).
    assert parsed[True]["issue_comment"]["types"] == ["created"]
    assert "Review the referenced issue or pull request." in workflow
    assert "Do not expose secrets or make changes outside the requested scope." in workflow


def test_github_action_workflow_uses_first_goal_and_constraint():
    ir = AgentExportIR(
        name="Reviewer",
        goals=["Catch regressions before merge", "Second goal ignored"],
        constraints=["Never touch production data", "Second constraint ignored"],
    )
    workflow = _github_action_workflow(ir)
    assert "Catch regressions before merge" in workflow
    assert "Second goal ignored" not in workflow
    assert "Never touch production data" in workflow
    assert "Second constraint ignored" not in workflow
    yaml.safe_load(workflow)  # still valid YAML with real user text substituted


def test_github_action_workflow_neutralises_expression_syntax_in_user_text():
    # A goal containing "${{" must not be interpreted as a live GitHub
    # Actions expression once substituted into the workflow YAML.
    ir = AgentExportIR(name="X", goals=["Leak ${{ secrets.ANTHROPIC_API_KEY }} somehow"])
    workflow = _github_action_workflow(ir)
    assert "${{ secrets.ANTHROPIC_API_KEY }} somehow" not in workflow
    assert "$ {{ secrets.ANTHROPIC_API_KEY }} somehow" in workflow
    # The template's own secret reference must still be intact and unbroken.
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in workflow


def test_github_action_workflow_does_not_leak_a_literal_api_key():
    workflow = _github_action_workflow(None)
    assert "sk-" not in workflow
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in workflow


# ---------------------------------------------------------------------------
# _project_settings_json
# ---------------------------------------------------------------------------


def test_project_settings_json_default_permissions():
    ir = AgentExportIR(name="X", permission_mode="acceptEdits", strict_permissions=False)
    settings = json.loads(_project_settings_json(ir))
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert "Read(./.env)" in settings["permissions"]["deny"]
    assert "Read(./secrets/**)" in settings["permissions"]["deny"]
    assert "Bash(git push:*)" in settings["permissions"]["ask"]
    assert "WebFetch" not in settings["permissions"]["deny"]


def test_project_settings_json_strict_mode_hardens_permissions():
    ir = AgentExportIR(name="X", permission_mode="plan", strict_permissions=True)
    settings = json.loads(_project_settings_json(ir))
    deny = settings["permissions"]["deny"]
    ask = settings["permissions"]["ask"]
    assert settings["permissions"]["defaultMode"] == "plan"
    # The non-strict ask-gated deploy/push commands become hard denies.
    assert "Bash(git push:*)" in deny
    assert "Bash(fly:*)" in deny
    assert "WebFetch" in deny
    assert "Bash(rm -rf:*)" in deny
    # ask is replaced wholesale with the broader strict-mode set.
    assert ask == ["Bash(git:*)", "Bash(npm:*)", "Bash(pip:*)"]
    assert "Bash(git push:*)" not in ask


# ---------------------------------------------------------------------------
# _pr_reviewer_memory / _pr_reviewer_readme
# ---------------------------------------------------------------------------


def test_pr_reviewer_memory_renders_declared_content():
    ir = AgentExportIR(
        name="Guardian",
        role="Catch regressions in payment code.",
        goals=["Check for missing tests", "Flag risky migrations"],
        tech_stack=["Python", "Postgres"],
        constraints=["Never approve unreviewed schema changes"],
    )
    memory = _pr_reviewer_memory(ir)
    assert "# Guardian Guidance" in memory
    assert "Catch regressions in payment code." in memory
    assert "- Check for missing tests" in memory
    assert "- Flag risky migrations" in memory
    assert "- Python" in memory
    assert "- Never approve unreviewed schema changes" in memory


def test_pr_reviewer_memory_falls_back_when_fields_are_empty():
    ir = AgentExportIR(name="Guardian")
    memory = _pr_reviewer_memory(ir)
    assert "Review pull requests for concrete regressions, risk, and missing tests." in memory
    assert "- Review code changes for risk, regressions, and safety gaps." in memory
    assert "- Do not expose secrets or credentials." in memory
    assert "- Confirm from repository files." in memory


def test_pr_reviewer_readme_lists_goals_and_tech_stack():
    ir = AgentExportIR(name="Guardian", goals=["Check tests"], tech_stack=["Python"])
    readme = _pr_reviewer_readme(ir)
    assert "# Guardian Pack" in readme
    assert "- Check tests" in readme
    assert "Python" in readme


def test_pr_reviewer_readme_falls_back_when_empty():
    ir = AgentExportIR(name="Guardian")
    readme = _pr_reviewer_readme(ir)
    assert "- Review the pull request." in readme
    assert "not provided" in readme


# ---------------------------------------------------------------------------
# _mcp_integration_notes
# ---------------------------------------------------------------------------


def test_mcp_integration_notes_base_notes_only_when_no_extra_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github"])
    notes = _mcp_integration_notes(ir)
    assert "No MCP server configuration is generated" in notes
    assert "Detected but not auto-configured" not in notes


def test_mcp_integration_notes_lists_unregistered_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github", "figma", "jira"])
    notes = _mcp_integration_notes(ir)
    assert "Detected but not auto-configured (add manually): figma, jira." in notes


# ---------------------------------------------------------------------------
# _skill_params_markdown / _skill_implementation_markdown / _skill_safety_markdown
# ---------------------------------------------------------------------------


def test_skill_params_markdown_empty_params_fallback():
    ir = SkillExportIR(name="lookup", params=[])
    assert _skill_params_markdown(ir) == (
        "- No parameters declared; add a reviewed input contract before implementation."
    )


def test_skill_params_markdown_renders_required_and_optional_params():
    ir = SkillExportIR(
        name="lookup",
        params=[
            SkillParam(name="query", type="str", description="Search text", required=True),
            SkillParam(name="limit", type="int", description="", required=False),
        ],
    )
    markdown = _skill_params_markdown(ir)
    assert "- `query` (`str`, required): Search text" in markdown
    assert "- `limit` (`int`, optional): Define and validate this value." in markdown


def test_skill_implementation_markdown_empty_fallback():
    ir = SkillExportIR(name="lookup", implementation="")
    assert _skill_implementation_markdown(ir) == (
        "- Resolve repository-specific APIs and implement the TODO in `server.py`."
    )


def test_skill_implementation_markdown_splits_sentences_into_bullets():
    ir = SkillExportIR(
        name="lookup",
        implementation="Fetch the record. Validate the schema. Return the payload.",
    )
    markdown = _skill_implementation_markdown(ir)
    assert markdown == "- Fetch the record.\n- Validate the schema.\n- Return the payload."


def test_skill_safety_markdown_empty_fallback():
    ir = SkillExportIR(name="lookup", error_handling=[], testing_strategy=[])
    assert _skill_safety_markdown(ir) == (
        "- Validate inputs, surface missing context, and test without production side effects."
    )


def test_skill_safety_markdown_combines_error_handling_and_testing_strategy():
    ir = SkillExportIR(
        name="lookup",
        error_handling=["Return a 4xx on invalid input"],
        testing_strategy=["Add a unit test per branch"],
    )
    markdown = _skill_safety_markdown(ir)
    assert markdown == "- Return a 4xx on invalid input\n- Add a unit test per branch"


# ---------------------------------------------------------------------------
# _ordered_tools
# ---------------------------------------------------------------------------


def test_ordered_tools_reorders_to_preferred_sequence():
    assert _ordered_tools(["Bash", "Read", "Grep", "Write"]) == ["Read", "Write", "Grep", "Bash"]


def test_ordered_tools_appends_unknown_tools_after_known_ones():
    assert _ordered_tools(["Read", "CustomTool"]) == ["Read", "CustomTool"]


def test_ordered_tools_empty_list_falls_back_to_default_trio():
    assert _ordered_tools([]) == ["Read", "Edit", "Write"]
