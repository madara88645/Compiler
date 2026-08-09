"""Direct unit tests for pure string-templating helpers in
app.adapters.agent_packs that are not covered by
tests/test_agent_packs_private_helpers.py: `_agent_name`, `_agent_role`,
and `_pack_specific_workflow`.
"""

from app.adapters.agent_packs import (
    AgentPackRequest,
    _agent_name,
    _agent_role,
    _pack_specific_workflow,
)


def _req(pack_type: str, project_type: str = "svc", stack: str = "Python, FastAPI"):
    return AgentPackRequest(
        project_type=project_type,
        stack=stack,
        goal="Add a health route",
        pack_type=pack_type,
    )


# --- _agent_name -------------------------------------------------------------


def test_agent_name_project_pack_suffix():
    assert _agent_name(_req("project-pack", project_type="MyApp")) == "MyApp Maintainer"


def test_agent_name_subagent_suffix():
    assert _agent_name(_req("subagent", project_type="MyApp")) == "MyApp Focused Agent"


def test_agent_name_pr_reviewer_suffix():
    assert _agent_name(_req("pr-reviewer", project_type="MyApp")) == "MyApp PR Reviewer"


def test_agent_name_mcp_tool_stub_suffix():
    assert _agent_name(_req("mcp-tool-stub", project_type="MyApp")) == "MyApp Tool"


# --- _agent_role ---------------------------------------------------------------


def test_agent_role_pr_reviewer_mentions_read_only_and_stack():
    role = _agent_role(_req("pr-reviewer", project_type="svc", stack="Python, FastAPI"))
    assert "read-only pull request reviewer for svc" in role
    assert "Python, FastAPI" in role


def test_agent_role_subagent_mentions_focused_and_stack():
    role = _agent_role(_req("subagent", project_type="svc", stack="Node, Express"))
    assert "focused Claude Code subagent for svc" in role
    assert "Node, Express" in role


def test_agent_role_project_pack_mentions_maintain_and_stack():
    role = _agent_role(_req("project-pack", project_type="svc", stack="Go"))
    assert "maintain svc" in role
    assert "Go" in role


def test_agent_role_mcp_tool_stub_falls_back_to_default_maintainer_role():
    # mcp-tool-stub is not special-cased, so it falls through to the same
    # generic "maintain" branch as project-pack.
    role = _agent_role(_req("mcp-tool-stub", project_type="svc", stack="Rust"))
    assert "maintain svc" in role
    assert "Rust" in role


# --- _pack_specific_workflow -----------------------------------------------------


def test_pack_specific_workflow_pr_reviewer():
    workflow = _pack_specific_workflow("pr-reviewer")
    assert "Review the diff" in workflow
    assert "without editing" in workflow


def test_pack_specific_workflow_subagent():
    workflow = _pack_specific_workflow("subagent")
    assert "Confirm the requested outcome and boundaries" in workflow
    assert "smallest evidence-backed" in workflow


def test_pack_specific_workflow_project_pack_default():
    workflow = _pack_specific_workflow("project-pack")
    assert "implement the smallest scoped change" in workflow


def test_pack_specific_workflow_mcp_tool_stub_uses_default_branch():
    # mcp-tool-stub is not special-cased, so it shares the generic default
    # workflow text with project-pack.
    assert _pack_specific_workflow("mcp-tool-stub") == _pack_specific_workflow("project-pack")
