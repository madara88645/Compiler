"""
langchain.py — Generate LangChain (LCEL) and LangGraph Python code from AgentExportIR.
"""
from __future__ import annotations

import textwrap
import yaml

from .agent_ir import AgentExportIR


def _escape_for_python_string(text: str) -> str:
    return text.replace('"""', '\\"\\"\\"')


# ---------------------------------------------------------------------------
# LangChain LCEL chain
# ---------------------------------------------------------------------------


def to_langchain_python(ir: AgentExportIR) -> str:
    """Return LangChain LCEL chain Python code."""
    prompt = _escape_for_python_string(ir.raw_system_prompt)
    return textwrap.dedent(
        f'''\
        from langchain_anthropic import ChatAnthropic
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        llm = ChatAnthropic(model="{ir.model}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """{prompt}"""),
            ("human", "{{input}}")
        ])

        chain = prompt | llm | StrOutputParser()

        # Usage
        result = chain.invoke({{"input": "Your task here"}})
        print(result)
    '''
    )


# ---------------------------------------------------------------------------
# LangGraph StateGraph agent
# ---------------------------------------------------------------------------


def to_langgraph_python(ir: AgentExportIR) -> str:
    """Return LangGraph StateGraph Python code."""
    if ir.is_multi_agent and ir.agents:
        return _to_langgraph_multi(ir)
    return _to_langgraph_single(ir)


def _to_langgraph_single(ir: AgentExportIR) -> str:
    prompt = _escape_for_python_string(ir.raw_system_prompt)
    safe_name = _to_snake(ir.name)
    return textwrap.dedent(
        f'''\
        from langgraph.graph import StateGraph, MessagesState, END
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import SystemMessage

        llm = ChatAnthropic(model="{ir.model}")

        SYSTEM_PROMPT = """{prompt}"""


        def {safe_name}_node(state: MessagesState):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
            response = llm.invoke(messages)
            return {{"messages": [response]}}


        graph = StateGraph(MessagesState)
        graph.add_node("{safe_name}", {safe_name}_node)
        graph.set_entry_point("{safe_name}")
        graph.add_edge("{safe_name}", END)

        app = graph.compile()

        # Usage
        result = app.invoke({{
            "messages": [{{"role": "user", "content": "Your task here"}}]
        }})
        print(result["messages"][-1].content)
    '''
    )


def _to_langgraph_multi(ir: AgentExportIR) -> str:
    """Multi-agent LangGraph with one node per agent connected sequentially."""
    lines = [
        "from langgraph.graph import StateGraph, MessagesState, END",
        "from langchain_anthropic import ChatAnthropic",
        "from langchain_core.messages import SystemMessage, HumanMessage",
        "",
        f'llm = ChatAnthropic(model="{ir.model}")',
        "",
    ]

    node_names: list[str] = []
    for i, agent in enumerate(ir.agents, start=1):
        safe_name = _to_snake(agent.name) or f"agent_{i}"
        escaped = _escape_for_python_string(agent.raw_system_prompt)
        lines += [
            f"# Agent {i}: {agent.name}",
            f'SYSTEM_PROMPT_{i} = """{escaped}"""',
            "",
            f"def {safe_name}_node(state: MessagesState):",
            f'    msgs = [SystemMessage(content=SYSTEM_PROMPT_{i})] + state["messages"]',
            "    response = llm.invoke(msgs)",
            '    return {"messages": [response]}',
            "",
        ]
        node_names.append(safe_name)

    lines += [
        "graph = StateGraph(MessagesState)",
    ]
    for name in node_names:
        lines.append(f'graph.add_node("{name}", {name}_node)')
    lines.append(f'graph.set_entry_point("{node_names[0]}")')
    for a, b in zip(node_names, node_names[1:]):
        lines.append(f'graph.add_edge("{a}", "{b}")')
    lines.append(f'graph.add_edge("{node_names[-1]}", END)')
    lines += [
        "",
        "app = graph.compile()",
        "",
        "# Usage",
        'result = app.invoke({"messages": [{"role": "user", "content": "Your task here"}]})',
        'print(result["messages"][-1].content)',
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangChain YAML config
# ---------------------------------------------------------------------------


def to_langchain_yaml(ir: AgentExportIR) -> str:
    """Return a minimal YAML config for the LangChain prompt."""
    config = {
        "model": ir.model,
        "system_prompt": ir.raw_system_prompt,
        "input_variables": ["input"],
        "template": "{input}",
    }
    return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_snake(name: str) -> str:
    """Convert an agent name to a safe Python snake_case identifier."""
    import re

    s = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip()).lower()
    return s or "agent"
