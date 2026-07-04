from __future__ import annotations

import json
import re
import shlex
import textwrap
from typing import Any

from .agent_ir import AgentExportIR
from .mcp_servers import render_mcp_json, unregistered_servers
from .skill_ir import SkillExportIR


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


def _escape_triple_quotes(text: str) -> str:
    return text.replace('"""', '\\"\\"\\"')


def _strip_markdown_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences from text."""
    text = text.strip()
    # Strip leading fence (```lang or just ```)
    text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
    # Strip trailing fence
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def to_agent_sdk_python(ir: AgentExportIR) -> str:
    prompt = _escape_triple_quotes(ir.raw_system_prompt)
    allowed_tools = ", ".join(f'"{tool}"' for tool in _ordered_tools(ir.allowed_tools))
    return textwrap.dedent(
        f"""\
        import asyncio
        from claude_agent_sdk import query, ClaudeAgentOptions


        async def main() -> None:
            async for message in query(
                prompt="Your task here",
                options=ClaudeAgentOptions(
                    system_prompt=\"\"\"{prompt}\"\"\",
                    allowed_tools=[{allowed_tools}],
                    model="{ir.model}",
                ),
            ):
                print(message)


        asyncio.run(main())
        """
    )


def to_agent_sdk_typescript(ir: AgentExportIR) -> str:
    prompt = ir.raw_system_prompt.replace("`", "\\`")
    allowed_tools = ", ".join(f'"{tool}"' for tool in _ordered_tools(ir.allowed_tools))
    return textwrap.dedent(
        f"""\
        import {{ query }} from "@anthropic-ai/claude-agent-sdk";

        const systemPrompt = `{prompt}`;

        const run = async () => {{
          for await (const message of query({{
            prompt: "Your task here",
            options: {{
              systemPrompt,
              allowedTools: [{allowed_tools}],
              model: "{ir.model}",
            }},
          }})) {{
            console.log(message);
          }}
        }};

        void run();
        """
    )


def to_claude_subagent(ir: AgentExportIR) -> dict[str, str]:
    slug = _slugify(ir.name)
    tools = ", ".join(ir.allowed_tools or ["Read", "Edit", "Write"])
    description = ir.role or (ir.goals[0] if ir.goals else f"Specialized assistant for {ir.name}")
    description_json = json.dumps(" ".join(description.split()))
    clean_prompt = _strip_markdown_fences(ir.raw_system_prompt)
    content = textwrap.dedent(
        f"""\
---
name: {slug}
description: {description_json}
tools: {tools}
---

{clean_prompt}
"""
    )
    return {"path": f".claude/agents/{slug}.md", "content": content}


def to_claude_project_pack(ir: AgentExportIR) -> list[dict[str, str]]:
    files = [
        {"path": "CLAUDE.md", "content": _project_claude_md(ir)},
        {"path": ".claude/settings.json", "content": _project_settings_json(ir)},
        to_claude_subagent(ir),
        {"path": ".github/workflows/claude.yml", "content": _github_action_workflow(ir)},
        {"path": ".claude/mcp/README.md", "content": _mcp_integration_notes(ir)},
    ]
    mcp_json = render_mcp_json(ir.mcp_servers)
    if mcp_json is not None:
        files.append({"path": ".mcp.json", "content": mcp_json})
    return files


def to_claude_subagent_bundle(ir: AgentExportIR) -> list[dict[str, str]]:
    subagent = to_claude_subagent(ir)
    goals = "\n".join(f"- {goal}" for goal in ir.goals) or "- Follow the agent goal."
    readme = textwrap.dedent(
        f"""\
# {ir.name} Subagent Bundle

Drop `{subagent["path"]}` into your repo, then ask Claude Code to use the `{_slugify(ir.name)}` subagent.

## Declared technology context

{", ".join(ir.tech_stack) or "Confirm the repository stack before acting."}

## Intended outcome

{goals}

## Install and verify

1. Review the agent instructions against the repository's own guidance.
2. Copy the file to the exact path shown above.
3. Invoke the subagent on a representative, non-production task.
4. Confirm its proposed files and validation commands before allowing edits.
"""
    )
    return [
        subagent,
        {"path": "README.md", "content": readme},
    ]


def to_claude_pr_reviewer_pack(ir: AgentExportIR) -> list[dict[str, str]]:
    reviewer = to_claude_subagent(ir)
    reviewer["path"] = ".claude/agents/pr-reviewer.md"
    files = [
        {"path": "CLAUDE.md", "content": _pr_reviewer_memory(ir)},
        {"path": ".claude/settings.json", "content": _project_settings_json(ir)},
        reviewer,
        {"path": ".github/workflows/claude.yml", "content": _github_action_workflow(ir)},
        {"path": "README.md", "content": _pr_reviewer_readme(ir)},
    ]
    mcp_json = render_mcp_json(ir.mcp_servers)
    if mcp_json is not None:
        files.append({"path": ".mcp.json", "content": mcp_json})
    return files


def to_claude_mcp_tool_stub(ir: SkillExportIR) -> list[dict[str, str]]:
    tool_name = ir.name
    param_signature = ", ".join(
        f"{param.name}: {param.type if param.type != 'Any' else 'str'}"
        + ("" if param.required else " | None = None")
        for param in ir.params
    )
    content = textwrap.dedent(
        f"""\
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{tool_name}")


@mcp.tool()
async def {tool_name}({param_signature}) -> str:
    \"\"\"{ir.purpose or f"Execute {tool_name}."}\"\"\"
    raise NotImplementedError("TODO: implement {tool_name}")


if __name__ == "__main__":
    mcp.run()
"""
    )
    readme = textwrap.dedent(
        f"""\
# {tool_name} MCP Tool Stub

## Purpose

{ir.purpose or f"Execute {tool_name}."}

## Input

{_skill_params_markdown(ir)}

## Output

{ir.output_description or f"Returns {ir.output_type}."}

## Implementation checklist

{_skill_implementation_markdown(ir)}

## Safety and verification

{_skill_safety_markdown(ir)}
"""
    )
    return [
        {"path": "server.py", "content": content},
        {"path": "README.md", "content": readme},
    ]


def _project_claude_md(ir: AgentExportIR) -> str:
    goals = (
        "\n".join(f"- {goal}" for goal in ir.goals[:4])
        or "- Preserve the existing product behavior."
    )
    constraints = (
        "\n".join(f"- {constraint}" for constraint in ir.constraints[:4])
        or "- Do not leak secrets."
    )
    workflows = (
        "\n".join(f"{index}. {step}" for index, step in enumerate(ir.workflows, start=1))
        or "1. Inspect the repository before changing it."
    )
    stack = "\n".join(f"- {item}" for item in ir.tech_stack) or "- Confirm from repository files."
    return textwrap.dedent(
        f"""\
# {ir.name} Project Guidance

## Project context

{ir.role or f"Work on {ir.name}."}

## Objectives

{goals}

## Constraints

{constraints}

## Workflow

{workflows}

## Declared technology context

{stack}

## Validation contract

- Read repository instructions and package configuration before choosing commands.
- Run the smallest relevant existing checks first, then the broader repository gate when available.
- Do not claim a test, build, deploy, or manual check passed unless it actually ran.
- Report changed files, out-of-scope changes, validation results, remaining risk, and one next step.

## Claude Code configuration

- Permission mode: `{ir.permission_mode}`
- Suggested tools: {", ".join(ir.allowed_tools) or "Read, Glob, Grep"}
"""
    )


def _select_post_edit_suggestions(ir: AgentExportIR) -> list[str]:
    """Hook suggestions that describe a post-edit action (test/lint/frontend build)."""
    return [
        s
        for s in ir.hook_suggestions
        if "after" in s.lower() and ("edit" in s.lower() or "code" in s.lower())
    ]


def _hooks_example_json(ir: AgentExportIR) -> str | None:
    """Render an example Claude Code hooks file from post-edit suggestions.

    Returns None when there is nothing to render. This is an *example* file the
    user adopts; it is never read live by Claude Code, so it does not nag on edits.
    The suggestion text is passed through shlex.quote so the echo command is valid
    shell for any content (no injection/expansion).
    """
    selected = _select_post_edit_suggestions(ir)
    if not selected:
        return None
    post_tool_use = [
        {
            "matcher": "Edit|Write",
            "hooks": [{"type": "command", "command": f"echo {shlex.quote(s)}"}],
        }
        for s in selected
    ]
    data = {
        "//": (
            'Example Claude Code hooks. Copy the "hooks" block into '
            ".claude/settings.json and replace each echo with your real command."
        ),
        "hooks": {"PostToolUse": post_tool_use},
    }
    return json.dumps(data, indent=2)


def _project_settings_json(ir: AgentExportIR) -> str:
    settings: dict[str, Any] = {
        "permissions": {
            "defaultMode": ir.permission_mode,
            "deny": [
                "Read(./.env)",
                "Read(./.env.*)",
                "Read(./**/.env)",
                "Read(./**/.env.*)",
                "Read(./secrets/**)",
                "Read(./**/*.pem)",
                "Read(./**/*.key)",
            ],
            "ask": [
                "Bash(git push:*)",
                "Bash(git commit:*)",
                "Bash(fly:*)",
                "Bash(vercel:*)",
                "Bash(kubectl:*)",
            ],
        }
    }
    return json.dumps(settings, indent=2)


def _named_subagent(name: str) -> str:
    descriptions = {
        "compiler-architect": "Plans compiler, export, and orchestration changes with an API-first mindset.",
        "prompt-safety-reviewer": "Reviews prompt changes for leakage, policy regressions, and unsafe instructions.",
        "mcp-integrator": "Builds and debugs MCP tools, bridges, and Claude/Cursor/Desktop integrations.",
        "frontend-polisher": "Improves product positioning, export UX, and responsive frontend details.",
    }
    prompts = {
        "compiler-architect": "Focus on IR contracts, adapters, routes, and backward compatibility.",
        "prompt-safety-reviewer": "Check for secret leaks, weak permissions, unsafe tool allowances, and missing guardrails.",
        "mcp-integrator": "Own stdio/HTTP MCP connectivity, endpoint contracts, and developer setup docs.",
        "frontend-polisher": "Keep the UI crisp, intentional, and focused on executable agent workflows.",
    }
    tools = {
        "compiler-architect": "Read, Edit, Write, Grep, Glob, Bash",
        "prompt-safety-reviewer": "Read, Grep, Glob",
        "mcp-integrator": "Read, Edit, Write, Grep, Glob, Bash",
        "frontend-polisher": "Read, Edit, Write, Grep, Glob, Bash",
    }
    return textwrap.dedent(
        f"""\
---
name: {name}
description: {descriptions[name]}
tools: {tools[name]}
---

{prompts[name]}
"""
    )


def _github_action_workflow(ir: AgentExportIR | None = None) -> str:
    goal = _workflow_scalar(
        ir.goals[0] if ir and ir.goals else "Review the referenced issue or pull request."
    )
    constraint = _workflow_scalar(
        ir.constraints[0]
        if ir and ir.constraints
        else "Do not expose secrets or make changes outside the requested scope."
    )
    template = textwrap.dedent(
        """\
name: Claude Code

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude:
    if: contains(github.event.comment.body, '@claude')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: >
            Follow CLAUDE.md and inspect the referenced issue or pull request.
            Goal: __PACK_GOAL__
            Constraint: __PACK_CONSTRAINT__
            Use repository evidence, report validation honestly, and require human review before merge.
          claude_args: "--max-turns 5"
"""
    )
    return template.replace("__PACK_GOAL__", goal).replace("__PACK_CONSTRAINT__", constraint)


def _workflow_scalar(value: str) -> str:
    """Keep request text inside the workflow's folded scalar."""

    return " ".join(value.split()).replace("${{", "$ {{")


def _pr_reviewer_memory(ir: AgentExportIR) -> str:
    goals = (
        "\n".join(f"- {goal}" for goal in ir.goals[:4])
        or "- Review code changes for risk, regressions, and safety gaps."
    )
    return textwrap.dedent(
        f"""\
# {ir.name} Guidance

## Mission
{ir.role or "Review pull requests for concrete regressions, risk, and missing tests."}

## Declared technology context
{chr(10).join(f"- {item}" for item in ir.tech_stack) or "- Confirm from repository files."}

## Review Checklist
{goals}

## Guardrails
{chr(10).join(f"- {item}" for item in ir.constraints) or "- Do not expose secrets or credentials."}

## Review output
- Lead with actionable findings, ordered by severity, and cite the affected file or diff evidence.
- Separate blockers from non-blocking suggestions.
- Report missing or unverified tests explicitly; never infer that CI passed.
- End with a concise merge recommendation and remaining risk.
"""
    )


def _pr_reviewer_readme(ir: AgentExportIR) -> str:
    goals = "\n".join(f"- {goal}" for goal in ir.goals) or "- Review the pull request."
    return textwrap.dedent(
        f"""\
# {ir.name} Pack

This pack gives Claude Code a dedicated `pr-reviewer` subagent and repository guidance for:

{goals}

## Verify before enabling automation

1. Review `CLAUDE.md` and `.claude/agents/pr-reviewer.md` against the repository's policies.
2. Confirm the declared technology context: {", ".join(ir.tech_stack) or "not provided"}.
3. Add `ANTHROPIC_API_KEY` to GitHub Actions only if your organization approves that integration.
4. Test the reviewer on a non-sensitive pull request and inspect its file citations and test claims.
"""
    )


def _mcp_integration_notes(ir: AgentExportIR) -> str:
    notes = textwrap.dedent(
        f"""\
# MCP integration notes for {ir.name}

No MCP server configuration is generated because the request did not provide a verified command or server path.

Before adding an MCP server:

1. Identify an existing server entry point in the repository.
2. Run it locally and confirm its tool schema.
3. Add the verified command to the host client's MCP configuration.
4. Keep secrets in the host environment; do not write credentials into this pack.
"""
    )
    extra = unregistered_servers(ir.mcp_servers)
    if extra:
        notes += f"\nDetected but not auto-configured (add manually): {', '.join(extra)}.\n"
    return notes


def _skill_params_markdown(ir: SkillExportIR) -> str:
    if not ir.params:
        return "- No parameters declared; add a reviewed input contract before implementation."
    return "\n".join(
        (
            f"- `{param.name}` (`{param.type}`, "
            f"{'required' if param.required else 'optional'}): "
            f"{param.description or 'Define and validate this value.'}"
        )
        for param in ir.params
    )


def _skill_implementation_markdown(ir: SkillExportIR) -> str:
    implementation = (ir.implementation or "").strip()
    if not implementation:
        return "- Resolve repository-specific APIs and implement the TODO in `server.py`."
    sentences = [sentence.strip() for sentence in implementation.split(". ") if sentence.strip()]
    return "\n".join(f"- {sentence.rstrip('.')}." for sentence in sentences)


def _skill_safety_markdown(ir: SkillExportIR) -> str:
    items = [*ir.error_handling, *ir.testing_strategy]
    if not items:
        items = [
            "Validate inputs, surface missing context, and test without production side effects."
        ]
    return "\n".join(f"- {item}" for item in items)


def _ordered_tools(tools: list[str]) -> list[str]:
    preferred_order = ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]
    pool = tools or ["Read", "Edit", "Write"]
    ordered = [tool for tool in preferred_order if tool in pool]
    ordered.extend(tool for tool in pool if tool not in ordered)
    return ordered
