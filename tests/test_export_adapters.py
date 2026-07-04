"""
tests/test_export_adapters.py — Tests for the Export Adapter layer.

Covers IR extraction, code generation, and API endpoints for both
agent and skill exports.
"""
from __future__ import annotations

import json

import pytest
import yaml
from fastapi.testclient import TestClient

from app.adapters.agent_ir import AgentExportIR, parse_agent_markdown
from app.adapters.claude_code import (
    to_agent_sdk_python,
    to_agent_sdk_typescript,
    to_claude_project_pack,
    to_claude_pr_reviewer_pack,
    to_claude_subagent,
    to_claude_mcp_tool_stub,
)
from app.adapters.claude_sdk import to_python, to_yaml
from app.adapters.langchain import to_langchain_python, to_langgraph_python
from app.adapters.skill_adapter import to_agent_skill, to_claude_tool_use, to_langchain_tool
from app.adapters.skill_ir import SkillExportIR, parse_skill_markdown


# ---------------------------------------------------------------------------
# Sample fixtures that mirror real agent_generator.md / skills_generator.md output
# ---------------------------------------------------------------------------

SINGLE_AGENT_MARKDOWN = """\
# Data Analyst Agent - System Prompt

## Role
You are an expert data analyst specializing in business intelligence and statistical analysis.

## Goals
- Analyze datasets and extract actionable insights
- Generate clear, concise reports for stakeholders
- Identify trends, anomalies, and patterns in data

## Constraints
- Never fabricate or hallucinate data points
- Always cite sources and confidence intervals
- Limit analysis to provided datasets only

## Workflows
1. Receive dataset and analysis requirements
2. Perform exploratory data analysis (EDA)
3. Apply appropriate statistical methods
4. Generate visual summaries where relevant
5. Compile findings into a structured report

## Tech Stack
- Python (pandas, numpy, matplotlib, seaborn)
- SQL for database queries
- Jupyter notebooks for interactive analysis

## Example Interaction
User: Analyze sales data for Q3 2024.
Agent: I'll begin with an EDA of the Q3 2024 sales dataset...
"""

MULTI_AGENT_MARKDOWN = """\
# Agent 1: Researcher

## Role
You are a research specialist that gathers information from multiple sources.

## Goals
- Collect relevant information based on query
- Summarise key findings concisely

## Constraints
- Only use verified information sources
- Cite all references

## Workflows
1. Receive research query
2. Identify relevant sources
3. → Passes summarised findings to Agent 2 via structured JSON

## Tech Stack
- Web search APIs
- Document parsing tools

---

# Agent 2: Writer

## Role
You are a professional technical writer who transforms research into polished documents.

## Goals
- Convert research findings into clear, readable prose
- Maintain consistent tone and style

## Constraints
- Do not add information not present in source material
- Keep output under 500 words unless instructed otherwise

## Workflows
1. Receive structured findings from Agent 1
2. Draft document outline
3. Write final document

## Tech Stack
- Markdown formatting
- Grammar checking tools
"""

SKILL_MARKDOWN = """\
# web_search - Skill Definition

## Name
web_search

## Purpose
Search the web for up-to-date information based on a user query and return relevant results.

## Input Schema
| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| query | string | The search query string | Yes |
| max_results | integer | Maximum number of results to return | No |

## Output Schema
Returns a list of search result objects, each containing title, url, and snippet fields.

## Implementation
1. Validate and sanitise the query string
2. Call the search API with the query and max_results parameters
3. Parse and normalise the response
4. Return structured results

## Dependencies
- requests
- beautifulsoup4

## Error Handling
- Return empty list if API is unavailable
- Raise ValueError for empty or invalid query strings
"""


# ---------------------------------------------------------------------------
# IR extraction tests
# ---------------------------------------------------------------------------


def test_parse_single_agent_ir():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)

    assert isinstance(ir, AgentExportIR)
    assert "Data Analyst" in ir.name
    assert "expert data analyst" in ir.role
    assert len(ir.goals) >= 3
    assert any("insights" in g.lower() for g in ir.goals)
    assert len(ir.constraints) >= 3
    assert len(ir.workflows) >= 4
    assert len(ir.tech_stack) >= 2
    assert ir.is_multi_agent is False
    assert ir.permission_mode == "acceptEdits"
    assert "Read" in ir.allowed_tools
    assert "Edit" in ir.allowed_tools
    assert ir.raw_system_prompt.strip() == SINGLE_AGENT_MARKDOWN.strip()


def test_parse_multi_agent_ir():
    ir = parse_agent_markdown(MULTI_AGENT_MARKDOWN)

    assert ir.is_multi_agent is True
    assert len(ir.agents) == 2
    assert ir.raw_system_prompt.strip() == MULTI_AGENT_MARKDOWN.strip()

    agent1, agent2 = ir.agents
    assert "Researcher" in agent1.name or "researcher" in agent1.role.lower()
    assert "Writer" in agent2.name or "writer" in agent2.role.lower()
    assert len(agent1.goals) >= 1
    assert len(agent2.goals) >= 1


def test_parse_agent_raw_prompt_preserved():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    assert ir.raw_system_prompt.strip() == SINGLE_AGENT_MARKDOWN.strip()


# ---------------------------------------------------------------------------
# Claude SDK output tests
# ---------------------------------------------------------------------------


def test_claude_sdk_python_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    code = to_python(ir)

    assert "from anthropic import Anthropic" in code
    assert "client.messages.create(" in code
    assert "claude-opus-4-6" in code
    assert "max_tokens=8096" in code
    assert "response.content[0].text" in code


def test_claude_sdk_yaml_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    yml = to_yaml(ir)

    parsed = yaml.safe_load(yml)
    assert parsed["model"] == "claude-opus-4-6"
    assert parsed["max_tokens"] == 8096
    assert "system" in parsed
    assert "Data Analyst" in parsed["system"]


def test_claude_agent_sdk_python_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    code = to_agent_sdk_python(ir)

    assert "from claude_agent_sdk import query, ClaudeAgentOptions" in code
    assert 'allowed_tools=["Read", "Edit", "Write"' in code
    assert "prompt=" in code


def test_claude_agent_sdk_typescript_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    code = to_agent_sdk_typescript(ir)

    assert 'import { query } from "@anthropic-ai/claude-agent-sdk"' in code
    assert "allowedTools" in code
    assert "claude-opus" in code


def test_claude_subagent_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    file_spec = to_claude_subagent(ir)

    assert file_spec["path"].startswith(".claude/agents/")
    assert file_spec["path"].endswith(".md")
    assert "name:" in file_spec["content"]
    assert "description:" in file_spec["content"]
    assert "tools:" in file_spec["content"]


def test_claude_subagent_frontmatter_starts_at_column_zero():
    """Verify agent file starts with --- at column 0 (no leading spaces)."""
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    file_spec = to_claude_subagent(ir)

    content = file_spec["content"]
    lines = content.split("\n")

    # First line must be exactly "---" with no leading spaces
    assert lines[0] == "---", f"Expected '---' at column 0, got: {repr(lines[0])}"

    # Find the closing frontmatter line
    closing_idx = None
    for idx, line in enumerate(lines[1:], start=1):
        if line == "---":
            closing_idx = idx
            break

    assert closing_idx is not None, "Missing closing --- in frontmatter"

    # Verify frontmatter fields have no leading spaces
    for line in lines[1:closing_idx]:
        if line.strip():  # Skip empty lines
            assert not line.startswith(" "), f"Frontmatter line has leading spaces: {repr(line)}"


def test_claude_subagent_no_stray_code_fences():
    """Verify agent file contains no stray markdown code fences."""
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    file_spec = to_claude_subagent(ir)

    content = file_spec["content"]
    lines = content.split("\n")

    # Count all ``` occurrences (should be 0 for regular agent markdown)
    fence_count = sum(1 for line in lines if line.strip().startswith("```"))
    assert fence_count == 0, f"Found {fence_count} stray code fence(s) in agent file"


def test_claude_subagent_strips_markdown_fences_from_prompt():
    """Verify markdown fences are stripped from raw_system_prompt."""
    # Create a markdown with code fences around it (simulating model output)
    fenced_markdown = "```markdown\n" + SINGLE_AGENT_MARKDOWN + "\n```"
    ir = parse_agent_markdown(fenced_markdown)

    file_spec = to_claude_subagent(ir)
    content = file_spec["content"]

    # Should not contain the wrapper fences
    assert not content.strip().startswith("```"), "Content starts with code fence"
    assert not content.strip().endswith("```"), "Content ends with code fence"

    # Should still contain the actual agent content
    assert "Data Analyst" in content or "expert data analyst" in content


def test_claude_project_pack_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    pack = to_claude_project_pack(ir)
    paths = {item["path"] for item in pack}

    assert "CLAUDE.md" in paths
    assert ".claude/settings.json" in paths
    assert ".github/workflows/claude.yml" in paths
    assert any(path.startswith(".claude/agents/") for path in paths)


def test_claude_project_pack_claude_md_starts_at_column_zero():
    """Verify CLAUDE.md starts with # at column 0 (no leading spaces)."""
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    pack = to_claude_project_pack(ir)

    claude_md = next(item for item in pack if item["path"] == "CLAUDE.md")
    content = claude_md["content"]
    lines = content.split("\n")

    # First line must start with # at column 0
    assert lines[0].startswith("#"), f"Expected heading at column 0, got: {repr(lines[0])}"
    assert not lines[0].startswith(" "), f"CLAUDE.md has leading spaces: {repr(lines[0])}"

    # Check that all markdown headings start at column 0
    for line in lines:
        if line.strip().startswith("#"):
            assert not line.startswith(" "), f"Heading has leading spaces: {repr(line)}"


def test_named_subagent_frontmatter_at_column_zero():
    """Verify named subagents have frontmatter at column 0."""
    from app.adapters.claude_code import _named_subagent

    for name in [
        "compiler-architect",
        "prompt-safety-reviewer",
        "mcp-integrator",
        "frontend-polisher",
    ]:
        content = _named_subagent(name)
        lines = content.split("\n")

        # First line must be exactly "---"
        assert lines[0] == "---", f"Agent {name}: Expected '---' at column 0, got: {repr(lines[0])}"

        # Find closing frontmatter
        closing_idx = None
        for idx, line in enumerate(lines[1:], start=1):
            if line == "---":
                closing_idx = idx
                break

        assert closing_idx is not None, f"Agent {name}: Missing closing --- in frontmatter"

        # Verify frontmatter fields have no leading spaces
        for line in lines[1:closing_idx]:
            if line.strip():
                assert not line.startswith(
                    " "
                ), f"Agent {name}: Frontmatter line has leading spaces: {repr(line)}"


def test_claude_mcp_tool_stub_output():
    ir = parse_skill_markdown(SKILL_MARKDOWN)
    stub = to_claude_mcp_tool_stub(ir)
    paths = {item["path"] for item in stub}

    assert "server.py" in paths
    assert "README.md" in paths
    server_file = next(item for item in stub if item["path"] == "server.py")
    assert "FastMCP" in server_file["content"]
    assert "web_search" in server_file["content"]


# ---------------------------------------------------------------------------
# LangChain output tests
# ---------------------------------------------------------------------------


def test_langchain_python_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    code = to_langchain_python(ir)

    assert "from langchain_anthropic import ChatAnthropic" in code
    assert "from langchain_core.prompts import ChatPromptTemplate" in code
    assert "StrOutputParser" in code
    assert "chain.invoke" in code
    assert "claude-opus-4-6" in code


def test_langgraph_python_output():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    code = to_langgraph_python(ir)

    assert "from langgraph.graph import StateGraph" in code
    assert "MessagesState" in code
    assert "SystemMessage" in code
    assert "graph.compile()" in code
    assert "app.invoke(" in code


def test_langgraph_multi_agent_output():
    ir = parse_agent_markdown(MULTI_AGENT_MARKDOWN)
    code = to_langgraph_python(ir)

    assert "StateGraph" in code
    assert "SYSTEM_PROMPT_1" in code
    assert "SYSTEM_PROMPT_2" in code
    # Two nodes should be added
    assert code.count("add_node(") == 2


# ---------------------------------------------------------------------------
# Skill IR extraction tests
# ---------------------------------------------------------------------------


def test_skill_ir_extraction():
    ir = parse_skill_markdown(SKILL_MARKDOWN)

    assert isinstance(ir, SkillExportIR)
    assert ir.name == "web_search"
    assert "search" in ir.purpose.lower()
    assert len(ir.params) >= 1
    query_param = next((p for p in ir.params if p.name == "query"), None)
    assert query_param is not None
    assert query_param.type == "str"
    assert query_param.required is True


# ---------------------------------------------------------------------------
# Skill adapter output tests
# ---------------------------------------------------------------------------


def test_langchain_tool_output():
    ir = parse_skill_markdown(SKILL_MARKDOWN)
    code = to_langchain_tool(ir)

    assert "@tool" in code
    assert "from langchain.tools import tool" in code
    assert "web_search" in code
    # Should contain a pydantic model since we have params
    assert "BaseModel" in code


def test_claude_tool_use_json():
    ir = parse_skill_markdown(SKILL_MARKDOWN)
    json_str = to_claude_tool_use(ir)

    parsed = json.loads(json_str)
    assert parsed["name"] == "web_search"
    assert "description" in parsed
    assert parsed["input_schema"]["type"] == "object"
    assert "query" in parsed["input_schema"]["properties"]
    assert "query" in parsed["input_schema"].get("required", [])


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from api.main import app

    return TestClient(app)


def test_export_api_endpoint_agent(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "claude-sdk",
            "output_type": "both",
            "is_multi_agent": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "python_code" in data
    assert "yaml_config" in data
    assert data["python_code"] is not None
    assert "client.messages.create" in data["python_code"]
    assert data["yaml_config"] is not None


def test_export_api_endpoint_skill(client):
    response = client.post(
        "/skills-generator/export",
        json={
            "skill_definition": SKILL_MARKDOWN,
            "format": "langchain-tool",
            "output_type": "both",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "python_code" in data
    assert "json_config" in data
    assert data["python_code"] is not None
    assert "@tool" in data["python_code"]
    assert data["json_config"] is not None

    parsed = json.loads(data["json_config"])
    assert parsed["name"] == "web_search"


def test_export_api_endpoint_agent_sdk_python(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "claude-agent-sdk-py",
            "output_type": "python",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "claude_agent_sdk" in data["python_code"]
    assert data["files"] == []


def test_export_api_endpoint_agent_sdk_typescript(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "claude-agent-sdk-ts",
            "output_type": "typescript",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "@anthropic-ai/claude-agent-sdk" in data["code"]


def test_export_api_endpoint_claude_subagent(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "claude-subagent",
            "output_type": "markdown",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["python_code"] is None
    assert len(data["files"]) == 1
    assert data["files"][0]["path"].startswith(".claude/agents/")


def test_export_api_endpoint_claude_project_pack(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "claude-project-pack",
            "output_type": "manifest",
        },
    )

    assert response.status_code == 200
    data = response.json()
    paths = {item["path"] for item in data["files"]}
    assert "CLAUDE.md" in paths
    assert ".claude/settings.json" in paths
    assert ".github/workflows/claude.yml" in paths


def test_export_api_endpoint_skill_mcp_stub(client):
    response = client.post(
        "/skills-generator/export",
        json={
            "skill_definition": SKILL_MARKDOWN,
            "format": "claude-mcp-tool-stub",
            "output_type": "python",
        },
    )

    assert response.status_code == 200
    data = response.json()
    paths = {item["path"] for item in data["files"]}
    assert "server.py" in paths
    assert "README.md" in paths


def test_export_api_endpoint_skill_agent_skill_format(client):
    response = client.post(
        "/skills-generator/export",
        json={
            "skill_definition": SKILL_MARKDOWN,
            "format": "agent-skill",
            "output_type": "markdown",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("markdown"), "agent-skill format must populate the `markdown` field"
    md = data["markdown"]
    assert md.startswith("---\n"), "SKILL.md must lead with YAML frontmatter"
    assert "name: web-search" in md
    assert "description:" in md
    assert "## Overview" in md


def test_agent_skill_renders_for_legacy_skill_markdown():
    """Backwards compatibility: legacy skill markdown (no **What:** / **Type:**) still renders."""
    ir = parse_skill_markdown(SKILL_MARKDOWN)
    skill_md = to_agent_skill(ir)
    assert skill_md.startswith("---\n")
    assert "name: web-search" in skill_md
    assert "## Inputs" in skill_md


def test_export_api_invalid_format(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "nonexistent-framework",
            "output_type": "python",
        },
    )
    assert response.status_code == 400


def test_export_api_invalid_agent_format_does_not_reflect_input(client):
    malicious_format = '<script>alert("pwnd")</script>'
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": malicious_format,
            "output_type": "python",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported format."}
    assert malicious_format not in response.text


def test_export_api_invalid_skill_format_does_not_reflect_input(client):
    malicious_format = '<img src=x onerror="alert(1)">'
    response = client.post(
        "/skills-generator/export",
        json={
            "skill_definition": SKILL_MARKDOWN,
            "format": malicious_format,
            "output_type": "python",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported format."}
    assert malicious_format not in response.text


def test_export_api_python_only(client):
    response = client.post(
        "/agent-generator/export",
        json={
            "system_prompt": SINGLE_AGENT_MARKDOWN,
            "format": "langchain",
            "output_type": "python",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["python_code"] is not None
    assert data["yaml_config"] is None


# ---------------------------------------------------------------------------
# B3 slice 1 — render dead IR fields (.mcp.json + hooks example)
# ---------------------------------------------------------------------------


def test_project_pack_emits_mcp_json_for_known_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github"])
    pack = to_claude_project_pack(ir)
    mcp_files = [f for f in pack if f["path"] == ".mcp.json"]
    assert len(mcp_files) == 1
    payload = json.loads(mcp_files[0]["content"])
    assert payload["mcpServers"]["github"]["url"] == "https://api.githubcopilot.com/mcp/"


def test_project_pack_no_mcp_json_when_no_servers():
    ir = AgentExportIR(name="X", mcp_servers=[])
    pack = to_claude_project_pack(ir)
    assert not any(f["path"] == ".mcp.json" for f in pack)


def test_pr_reviewer_pack_emits_mcp_json():
    ir = AgentExportIR(name="X", mcp_servers=["slack"])
    pack = to_claude_pr_reviewer_pack(ir)
    assert any(f["path"] == ".mcp.json" for f in pack)


def test_mcp_readme_notes_unregistered_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github", "figma", "jira"])
    pack = to_claude_project_pack(ir)
    readme = next(f for f in pack if f["path"] == ".claude/mcp/README.md")
    assert "figma" in readme["content"]
    assert "jira" in readme["content"]


def test_mcp_readme_no_note_when_all_registered():
    ir = AgentExportIR(name="X", mcp_servers=["github"])
    pack = to_claude_project_pack(ir)
    readme = next(f for f in pack if f["path"] == ".claude/mcp/README.md")
    assert "not auto-configured" not in readme["content"]
