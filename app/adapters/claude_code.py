from __future__ import annotations

import json
import re
import textwrap
from typing import Any

from .agent_ir import AgentExportIR
from .skill_ir import SkillExportIR


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


def _escape_triple_quotes(text: str) -> str:
    return text.replace('"""', '\\"\\"\\"')


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
    content = textwrap.dedent(
        f"""\
        ---
        name: {slug}
        description: {description}
        tools: {tools}
        ---

        {ir.raw_system_prompt.strip()}
        """
    )
    return {"path": f".claude/agents/{slug}.md", "content": content}


def to_claude_project_pack(ir: AgentExportIR) -> list[dict[str, str]]:
    files = [
        {"path": "CLAUDE.md", "content": _project_claude_md(ir)},
        {"path": ".claude/settings.json", "content": _project_settings_json(ir)},
        to_claude_subagent(ir),
        {
            "path": ".claude/agents/compiler-architect.md",
            "content": _named_subagent("compiler-architect"),
        },
        {
            "path": ".claude/agents/prompt-safety-reviewer.md",
            "content": _named_subagent("prompt-safety-reviewer"),
        },
        {"path": ".claude/agents/mcp-integrator.md", "content": _named_subagent("mcp-integrator")},
        {
            "path": ".claude/agents/frontend-polisher.md",
            "content": _named_subagent("frontend-polisher"),
        },
        {"path": ".github/workflows/claude.yml", "content": _github_action_workflow()},
        {"path": ".claude/mcp/claude-desktop.json", "content": _mcp_config_snippet(ir)},
    ]
    return files


def to_claude_subagent_bundle(ir: AgentExportIR) -> list[dict[str, str]]:
    subagent = to_claude_subagent(ir)
    readme = textwrap.dedent(
        f"""\
        # Claude Subagent Bundle

        Drop `{subagent["path"]}` into your repo, then ask Claude Code to use the `{_slugify(ir.name)}` subagent.

        Recommended usage:
        - Keep `CLAUDE.md` in the repo root for shared guidance.
        - Add `.claude/settings.json` if you want permission guardrails alongside this agent.
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
        {"path": ".github/workflows/claude.yml", "content": _github_action_workflow()},
        {"path": "README.md", "content": _pr_reviewer_readme()},
    ]
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
            return "TODO: implement {tool_name}"


        if __name__ == "__main__":
            mcp.run()
        """
    )
    readme = textwrap.dedent(
        f"""\
        # {tool_name} MCP Tool Stub

        Generated from Prompt Compiler for Claude Code / MCP workflows.

        Purpose: {ir.purpose}
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
    mcp_servers = ", ".join(ir.mcp_servers) if ir.mcp_servers else "none yet"
    return textwrap.dedent(
        f"""\
        # Prompt Compiler Claude Code Memory

        ## Project Summary
        Prompt Compiler is a FastAPI + Next.js product that turns vague requests into structured prompts, execution plans, policy layers, agent packs, and workflow artifacts.

        ## Working Rules
        - Start from repo-root commands.
        - Prefer targeted tests before broad suites.
        - Respect API/auth boundaries and never expose secrets.
        - Keep provider integrations framework-agnostic unless the export surface is explicitly Claude-native.

        ## Domain Concepts
        {goals}

        ## Constraints
        {constraints}

        ## Runbook
        - Backend: `python -m uvicorn api.main:app --reload --port 8080`
        - Frontend: `cd web && npm run dev`
        - Python tests: `python -m pytest tests/ -q`
        - Frontend tests: `cd web && npm run test`

        ## Claude-Native Notes
        - Permission mode: `{ir.permission_mode}`
        - Suggested tools: {", ".join(ir.allowed_tools)}
        - Suggested MCP servers: {mcp_servers}
        """
    )


def _project_settings_json(ir: AgentExportIR) -> str:
    settings: dict[str, Any] = {
        "permissions": {
            "defaultMode": ir.permission_mode,
            "deny": [
                "Read(./.env)",
                "Read(./.env.*)",
                "Read(./secrets/**)",
                "Read(./users.db)",
                "Read(./web/.env.local)",
            ],
            "ask": [
                "Bash(git push:*)",
                "Bash(fly:*)",
            ],
        }
    }
    return json.dumps(settings, indent=2)


def _mcp_config_snippet(ir: AgentExportIR) -> str:
    command = ["python", "integrations/mcp-server/server.py"]
    config = {
        "mcpServers": {
            _slugify(ir.name): {
                "command": command[0],
                "args": command[1:],
            }
        }
    }
    return json.dumps(config, indent=2)


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


def _github_action_workflow() -> str:
    return textwrap.dedent(
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
                    Follow CLAUDE.md, inspect the referenced issue or PR context,
                    and respond or create changes only when the request is actionable.
                  claude_args: "--max-turns 5"
        """
    )


def _pr_reviewer_memory(ir: AgentExportIR) -> str:
    goals = (
        "\n".join(f"- {goal}" for goal in ir.goals[:4])
        or "- Review code changes for risk, regressions, and safety gaps."
    )
    return textwrap.dedent(
        f"""\
        # Claude PR Reviewer Memory

        ## Mission
        Review pull requests with a focus on prompt safety, secret handling, permission boundaries, and missing tests.

        ## Repo Context
        - Project type: repo-specific software product
        - Default review posture: skeptical, concrete, and test-aware

        ## Review Checklist
        {goals}

        ## Guardrails
        - Do not expose secrets or credentials.
        - Flag unsafe `.claude/settings.json` permissions.
        - Call out prompt leakage, weak validation, and missing regression coverage.
        """
    )


def _pr_reviewer_readme() -> str:
    return textwrap.dedent(
        """\
        # Claude PR Reviewer Pack

        This pack gives Claude Code a dedicated `pr-reviewer` subagent plus review-focused repo memory.

        Suggested prompts:
        - `Use the pr-reviewer subagent to review this pull request for prompt leakage and unsafe settings.`
        - `Review this diff for missing tests, secret exposure, and MCP misconfiguration.`
        """
    )


def _ordered_tools(tools: list[str]) -> list[str]:
    preferred_order = ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"]
    pool = tools or ["Read", "Edit", "Write"]
    ordered = [tool for tool in preferred_order if tool in pool]
    ordered.extend(tool for tool in pool if tool not in ordered)
    return ordered
