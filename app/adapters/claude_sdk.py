"""
claude_sdk.py — Generate Claude SDK-compatible Python code and YAML config from AgentExportIR.
"""

from __future__ import annotations

import textwrap
import yaml

from .agent_ir import AgentExportIR


def _escape_for_python_string(text: str) -> str:
    """Escape triple-quotes so the prompt can safely be embedded in a \"\"\" string."""
    return text.replace('"""', '\\"\\"\\"')


def _indent_yaml_block(text: str, indent: int = 2) -> str:
    """Indent every line of text for a YAML literal block scalar."""
    prefix = " " * indent
    return "\n".join(prefix + line for line in text.splitlines())


# ---------------------------------------------------------------------------
# Python code generation
# ---------------------------------------------------------------------------


def to_python(ir: AgentExportIR) -> str:
    """Return ready-to-run Python code using the anthropic SDK."""
    prompt = _escape_for_python_string(ir.raw_system_prompt)
    return textwrap.dedent(
        f'''\
        from anthropic import Anthropic

        client = Anthropic()

        response = client.messages.create(
            model="{ir.model}",
            max_tokens=8096,
            system="""{prompt}""",
            messages=[
                {{"role": "user", "content": "Your task here"}}
            ]
        )
        print(response.content[0].text)
    '''
    )


def to_python_multi(ir: AgentExportIR) -> str:
    """
    Return Python code for a multi-agent swarm using the anthropic SDK.
    Each agent is represented as a separate system prompt; the user orchestrates
    calls sequentially (simplest pattern for a middleware tool output).
    """
    if not ir.agents:
        return to_python(ir)

    lines = [
        "from anthropic import Anthropic",
        "",
        "client = Anthropic()",
        "",
    ]

    for i, agent in enumerate(ir.agents, start=1):
        var_name = f"agent_{i}_prompt"
        escaped = _escape_for_python_string(agent.raw_system_prompt)
        lines.append(f"# Agent {i}: {agent.name}")
        lines.append(f'{var_name} = """{escaped}"""')
        lines.append("")

    lines += [
        "def call_agent(system_prompt: str, user_message: str) -> str:",
        "    response = client.messages.create(",
        f'        model="{ir.model}",',
        "        max_tokens=8096,",
        "        system=system_prompt,",
        '        messages=[{"role": "user", "content": user_message}]',
        "    )",
        "    return response.content[0].text",
        "",
        "# Orchestrate: pipe output of one agent as input to the next",
    ]

    for i, agent in enumerate(ir.agents, start=1):
        if i == 1:
            lines.append(f'result_{i} = call_agent(agent_{i}_prompt, "Your initial task here")')
        else:
            lines.append(f"result_{i} = call_agent(agent_{i}_prompt, result_{i - 1})")

    lines.append(f"print(result_{len(ir.agents)})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# YAML config generation
# ---------------------------------------------------------------------------


def to_yaml(ir: AgentExportIR) -> str:
    """Return YAML config suitable for anthropic messages.create()."""
    config = {
        "model": ir.model,
        "max_tokens": 8096,
        "system": ir.raw_system_prompt,
        "messages": [{"role": "user", "content": "Your task here"}],
    }
    return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
