from app.adapters.agent_ir import parse_agent_markdown
from app.adapters.claude_sdk import to_python_multi, _indent_yaml_block

MULTI_AGENT_MARKDOWN = """# Agent 1: Researcher

## Role
You are a research specialist.

## Goals
- Collect information

---

# Agent 2: Writer

## Role
You are a professional writer.
"""


def test_to_python_multi_agent():
    ir = parse_agent_markdown(MULTI_AGENT_MARKDOWN)
    assert ir.is_multi_agent is True
    assert len(ir.agents) == 2

    code = to_python_multi(ir)

    assert "agent_1_prompt" in code
    assert "agent_2_prompt" in code
    assert "call_agent" in code
    assert "result_1 = call_agent" in code
    assert "result_2 = call_agent" in code
    assert "print(result_2)" in code


def test_to_python_multi_single_agent():
    # If called with a single agent, it should fallback to to_python
    markdown = """# Data Analyst Agent
## Role
You analyze data.
"""
    ir = parse_agent_markdown(markdown)
    assert ir.is_multi_agent is False

    code = to_python_multi(ir)
    assert "from anthropic import Anthropic" in code
    assert "client = Anthropic()" in code


def test_indent_yaml_block():
    text = "line 1\nline 2"
    indented = _indent_yaml_block(text, indent=4)
    assert indented == "    line 1\n    line 2"
