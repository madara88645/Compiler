"""
agent_ir.py — Parse Agent Generator markdown output into a structured IR.

The Agent Generator produces consistent section headers (## Role, ## Goals, etc.).
We exploit this to extract structured data without any LLM call.
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, Field


# Canonical section header aliases → IR field names
_SECTION_ALIASES: dict[str, str] = {
    "role": "role",
    "persona": "role",
    "goals": "goals",
    "goal": "goals",
    "objective": "goals",
    "objectives": "goals",
    "constraints": "constraints",
    "constraint": "constraints",
    "rules": "constraints",
    "rule": "constraints",
    "limitations": "constraints",
    "workflows": "workflows",
    "workflow": "workflows",
    "steps": "workflows",
    "tech stack": "tech_stack",
    "tech": "tech_stack",
    "technology stack": "tech_stack",
    "tools": "tech_stack",
    "tools & capabilities": "tech_stack",
    "tools and capabilities": "tech_stack",
    "capabilities": "tech_stack",
}


class AgentExportIR(BaseModel):
    """Structured intermediate representation of a generated agent system prompt."""

    name: str = "AI Agent"
    role: str = ""
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    model: str = "claude-opus-4-6"
    is_multi_agent: bool = False
    agents: list["AgentExportIR"] = Field(default_factory=list)
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] = Field(default_factory=list)
    hook_suggestions: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    ci_automation_intent: list[str] = Field(default_factory=list)
    memory_outline: list[str] = Field(default_factory=list)
    raw_system_prompt: str = ""  # always the full original markdown


AgentExportIR.model_rebuild()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_bullets(text: str) -> list[str]:
    """Extract bullet list items from a text block."""
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "• ")):
            item = stripped[2:].strip()
            if item:
                items.append(item)
        elif re.match(r"^\d+\.\s", stripped):
            item = re.sub(r"^\d+\.\s+", "", stripped).strip()
            if item:
                items.append(item)
    return items


def _extract_title(markdown: str) -> str:
    """Extract the agent name from the first # heading."""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            # Strip common suffixes like " - System Prompt"
            title = re.sub(
                r"\s{0,50}[-–]\s{0,50}(system\s{1,50}prompt|prompt)$",
                "",
                title,
                flags=re.IGNORECASE,
            )
            return title.strip()
    return "AI Agent"


def _parse_sections(markdown: str) -> dict[str, str]:
    """Split markdown into {section_key: content} using ## headers."""
    sections: dict[str, str] = {}
    current_key: Optional[str] = None
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip().lower()
            current_lines = []
        elif line.startswith("# ") and not line.startswith("## "):
            # Top-level title — save if we have a pending section
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
                current_key = None
                current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _map_sections(sections: dict[str, str]) -> dict[str, str]:
    """Normalise section keys using alias table."""
    mapped: dict[str, str] = {}
    for raw_key, content in sections.items():
        canonical = _SECTION_ALIASES.get(raw_key)
        if canonical and canonical not in mapped:
            mapped[canonical] = content
    return mapped


def _build_ir(markdown: str, is_multi_agent: bool = False) -> AgentExportIR:
    """Build a single AgentExportIR from one agent block."""
    sections_raw = _parse_sections(markdown)
    sections = _map_sections(sections_raw)

    name = _extract_title(markdown)

    role = sections.get("role", "").strip()
    goals = _parse_bullets(sections.get("goals", ""))
    constraints = _parse_bullets(sections.get("constraints", ""))
    workflows = _parse_bullets(sections.get("workflows", ""))
    tech_stack = _parse_bullets(sections.get("tech_stack", ""))
    combined_text = "\n".join([name, role, *goals, *constraints, *workflows, *tech_stack]).lower()

    return AgentExportIR(
        name=name,
        role=role,
        goals=goals,
        constraints=constraints,
        workflows=workflows,
        tech_stack=tech_stack,
        is_multi_agent=is_multi_agent,
        allowed_tools=_infer_allowed_tools(combined_text),
        hook_suggestions=_infer_hook_suggestions(combined_text),
        mcp_servers=_infer_mcp_servers(combined_text),
        ci_automation_intent=_infer_ci_automation_intent(combined_text),
        memory_outline=_infer_memory_outline(
            name=name, role=role, goals=goals, constraints=constraints
        ),
        raw_system_prompt=markdown.strip(),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_agent_markdown(markdown: str) -> AgentExportIR:
    """
    Parse Agent Generator markdown output into AgentExportIR.

    For multi-agent output (blocks separated by '---'), returns a parent IR
    with individual agents in `.agents` and the full prompt in `.raw_system_prompt`.
    """
    markdown = markdown.strip()

    # Detect multi-agent: look for agent-level `# Agent N:` headings after a `---`
    # The multi-agent planner separates agents with a bare '---' line.
    agent_blocks = _split_multi_agent_blocks(markdown)

    if len(agent_blocks) > 1:
        agents = [_build_ir(block, is_multi_agent=False) for block in agent_blocks]
        # Use first agent's name as swarm name, or generic
        swarm_name = "Multi-Agent Swarm"
        return AgentExportIR(
            name=swarm_name,
            is_multi_agent=True,
            agents=agents,
            raw_system_prompt=markdown,
        )

    return _build_ir(markdown, is_multi_agent=False)


def _split_multi_agent_blocks(markdown: str) -> list[str]:
    """
    Split multi-agent markdown on bare '---' separators that appear between agent
    blocks (not inside fenced code or yaml front-matter).
    """
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False

    for line in markdown.splitlines():
        stripped = line.strip()

        # Track fenced code blocks so we don't split on --- inside them
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence

        if not in_fence and stripped == "---":
            block_text = "\n".join(current).strip()
            if block_text:
                blocks.append(block_text)
            current = []
        else:
            current.append(line)

    tail = "\n".join(current).strip()
    if tail:
        blocks.append(tail)

    return blocks


def _infer_allowed_tools(text: str) -> list[str]:
    tools = {"Read", "Edit", "Write", "Glob", "Grep"}
    if any(
        keyword in text for keyword in ("code", "react", "python", "typescript", "debug", "build")
    ):
        tools.add("Bash")
    if any(keyword in text for keyword in ("web", "research", "search", "source", "docs")):
        tools.update({"WebSearch", "WebFetch"})
    if "github" in text or "pull request" in text or "pr " in text:
        tools.add("Bash")
    return sorted(tools)


def _infer_hook_suggestions(text: str) -> list[str]:
    suggestions = [
        "Block reads of .env and secrets before tool execution.",
        "Run targeted tests or lint checks after code edits.",
    ]
    if any(keyword in text for keyword in ("frontend", "react", "ui")):
        suggestions.append("Run frontend lint/build hooks after editing TSX or CSS.")
    if any(keyword in text for keyword in ("deploy", "ci", "release")):
        suggestions.append("Require human confirmation before git push or deploy commands.")
    return suggestions


def _infer_mcp_servers(text: str) -> list[str]:
    mapping = {
        "github": "github",
        "figma": "figma",
        "slack": "slack",
        "notion": "notion",
        "jira": "jira",
        "sentry": "sentry",
    }
    return [server for keyword, server in mapping.items() if keyword in text]


def _infer_ci_automation_intent(text: str) -> list[str]:
    intents: list[str] = []
    if any(keyword in text for keyword in ("review", "pull request", "pr ")):
        intents.append("review")
    if any(keyword in text for keyword in ("issue", "implement", "feature", "bug")):
        intents.append("implementation")
    if any(keyword in text for keyword in ("fix", "autofix", "failing test", "flaky")):
        intents.append("autofix")
    return intents


def _infer_memory_outline(
    *, name: str, role: str, goals: list[str], constraints: list[str]
) -> list[str]:
    outline = [f"Agent name: {name}"]
    if role:
        outline.append(f"Primary role: {role}")
    outline.extend(f"Goal: {goal}" for goal in goals[:3])
    outline.extend(f"Constraint: {constraint}" for constraint in constraints[:3])
    return outline
