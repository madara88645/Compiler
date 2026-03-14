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
from app.adapters.claude_sdk import to_python, to_yaml
from app.adapters.langchain import to_langchain_python, to_langgraph_python
from app.adapters.skill_adapter import to_claude_tool_use, to_langchain_tool
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
