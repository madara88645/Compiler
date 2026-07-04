from __future__ import annotations

import io
import re
from typing import Any, Literal, Protocol
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

from .agent_ir import AgentExportIR, parse_agent_markdown
from .claude_code import (
    to_claude_mcp_tool_stub,
    to_claude_pr_reviewer_pack,
    to_claude_project_pack,
    to_claude_subagent_bundle,
)
from .skill_ir import SkillExportIR, SkillParam, parse_skill_markdown
from app.readiness.analyzer import analyze_readiness
from app.readiness.markdown import report_to_markdown

PackType = Literal["project-pack", "subagent", "pr-reviewer", "mcp-tool-stub"]
RiskMode = Literal["balanced", "strict"]
AgentPackProvider = Literal["claude"]
AgentPackFileKind = Literal["claude_md", "settings", "agents", "workflow", "mcp", "readme", "files"]


class AgentPackRequest(BaseModel):
    project_type: str = Field(..., min_length=1, max_length=120)
    stack: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=8_000)
    pack_type: PackType
    risk_mode: RiskMode = "balanced"
    detected_commands: dict[str, str] | None = None
    detected_stack: str | None = None
    has_existing_claude_md: bool = False


class AgentPackFile(BaseModel):
    path: str
    content: str
    kind: AgentPackFileKind


class AgentPackManifest(BaseModel):
    provider: AgentPackProvider
    pack_type: PackType
    files: list[AgentPackFile]
    download_name: str
    preview_order: list[AgentPackFileKind]

    @model_validator(mode="after")
    def validate_preview_order(self) -> "AgentPackManifest":
        file_kinds = {file.kind for file in self.files}
        unknown_preview_kinds = [kind for kind in self.preview_order if kind not in file_kinds]
        if unknown_preview_kinds:
            joined = ", ".join(unknown_preview_kinds)
            raise ValueError(f"preview_order includes kinds without matching files: {joined}")
        normalized_paths: set[str] = set()
        for file in self.files:
            normalized_path = _normalize_pack_path(file.path)
            if normalized_path in normalized_paths:
                raise ValueError(f"duplicate file path in manifest: {file.path}")
            normalized_paths.add(normalized_path)
        return self


class AgentPackAdapter(Protocol):
    provider: str

    def build_manifest(self, req: AgentPackRequest, compiler: Any) -> AgentPackManifest:
        ...


class ClaudeAgentPackAdapter:
    provider = "claude"

    def build_manifest(self, req: AgentPackRequest, compiler: Any) -> AgentPackManifest:
        raw_files: list[dict[str, str]]

        if req.pack_type == "mcp-tool-stub":
            skill_definition = compiler.generate_skill(
                _build_skill_brief(req),
                include_example_code=False,
            )
            skill_ir = _build_skill_ir(req, skill_definition)
            raw_files = to_claude_mcp_tool_stub(skill_ir)
        else:
            system_prompt = compiler.generate_agent(
                _build_agent_brief(req),
                multi_agent=False,
                include_example_code=False,
            )
            agent_ir = _build_agent_ir(req, system_prompt)

            if req.pack_type == "project-pack":
                raw_files = to_claude_project_pack(agent_ir)
            elif req.pack_type == "subagent":
                raw_files = to_claude_subagent_bundle(agent_ir)
            else:
                raw_files = to_claude_pr_reviewer_pack(agent_ir)

        # Surface the readiness verdict in the first markdown file of the pack so the
        # exported artifact (preview and download alike) carries the same guidance.
        readiness_markdown = report_to_markdown(analyze_readiness(req.goal))
        for file in raw_files:
            if file["path"].endswith(".md"):
                file["content"] = f"{file['content'].rstrip()}\n\n{readiness_markdown}"
                break

        files = [
            AgentPackFile(
                path=file["path"], content=file["content"], kind=_classify_kind(file["path"])
            )
            for file in raw_files
        ]
        # Bolt Optimization: pre-compute a set of file kinds for O(1) lookups rather than a nested any() loop
        file_kinds = {file.kind for file in files}
        preview_order = [kind for kind in _preview_order() if kind in file_kinds]
        download_name = _build_download_name(req)

        return AgentPackManifest(
            provider=self.provider,
            pack_type=req.pack_type,
            files=files,
            download_name=download_name,
            preview_order=preview_order,
        )


AGENT_PACK_ADAPTERS: dict[str, AgentPackAdapter] = {
    "claude": ClaudeAgentPackAdapter(),
}


def create_download_response(manifest: AgentPackManifest) -> Response:
    if len(manifest.files) == 1:
        file = manifest.files[0]
        media_type = _media_type_for_path(file.path)
        filename = file.path.rsplit("/", 1)[-1]
        return Response(
            content=file.content.encode("utf-8"),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for file in manifest.files:
            archive.writestr(file.path, file.content)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{manifest.download_name}.zip"'},
    )


def _build_agent_brief(req: AgentPackRequest) -> str:
    pack_labels = {
        "project-pack": "full project pack for repo-aware Claude Code usage",
        "subagent": "focused Claude subagent",
        "pr-reviewer": "PR reviewer pack for code review and safety checks",
        "mcp-tool-stub": "MCP tool stub",
    }
    risk_line = (
        "Use strict security defaults, conservative tool permissions, and emphasize secret protection."
        if req.risk_mode == "strict"
        else "Balance usability with strong default safeguards and repo-safe behavior."
    )
    review_line = ""
    if req.pack_type == "pr-reviewer":
        review_line = (
            "\nThe agent must review pull requests for prompt leakage, unsafe settings, secret exposure, "
            "missing tests, and architecture risks."
        )

    return (
        f"Create a {pack_labels[req.pack_type]}.\n"
        f"Project type: {req.project_type}\n"
        f"Stack: {req.detected_stack or req.stack}\n"
        f"Goal: {req.goal}\n"
        f"{risk_line}{review_line}\n"
        "Write the output as a practical system prompt that can be exported into Claude-native assets."
    )


def _build_skill_brief(req: AgentPackRequest) -> str:
    risk_line = (
        "Favor strict validation, safe defaults, and defensive error handling."
        if req.risk_mode == "strict"
        else "Favor clean developer ergonomics with sensible guardrails."
    )
    return (
        "Generate a Claude-compatible MCP tool skill definition.\n"
        f"Project type: {req.project_type}\n"
        f"Stack: {req.stack}\n"
        f"Goal: {req.goal}\n"
        f"{risk_line}\n"
        "Include the purpose, parameters, expected behavior, and integration notes."
    )


def _validation_workflow(req: AgentPackRequest) -> str:
    cmds = req.detected_commands or {}
    if cmds:
        pairs = ", ".join(f"{name}: `{cmd}`" for name, cmd in cmds.items())
        return (
            f"Run the repository's real validation commands ({pairs}); "
            "report commands, results, remaining risk, and files changed."
        )
    return (
        "Discover the repository's existing validation commands, run the smallest relevant checks, "
        "and report commands, results, remaining risk, and files changed."
    )


def _classify_kind(path: str) -> AgentPackFileKind:
    normalized = path.replace("\\", "/")
    if normalized == "CLAUDE.md":
        return "claude_md"
    if normalized.endswith("settings.json"):
        return "settings"
    if "/agents/" in normalized:
        return "agents"
    if normalized.endswith("server.py") or "mcp" in normalized.lower():
        return "mcp"
    if normalized.startswith(".github/workflows/") or normalized.endswith(".yml"):
        return "workflow"
    if normalized.endswith("README.md"):
        return "readme"
    return "files"


def _preview_order() -> list[AgentPackFileKind]:
    return ["claude_md", "settings", "agents", "workflow", "mcp", "readme", "files"]


def _build_download_name(req: AgentPackRequest) -> str:
    return _slugify(f"{req.project_type}-{req.pack_type}-claude")


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "agent-pack"


def _media_type_for_path(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".md"):
        return "text/markdown; charset=utf-8"
    if path.endswith(".yml") or path.endswith(".yaml"):
        return "application/yaml"
    if path.endswith(".py"):
        return "text/x-python; charset=utf-8"
    return "text/plain; charset=utf-8"


def _normalize_pack_path(path: str) -> str:
    trimmed = path.strip()
    if not trimmed:
        raise ValueError("manifest file paths must not be empty")

    normalized = trimmed.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"manifest file path must be relative: {path}")

    parts = normalized.split("/")
    # Bolt Optimization: Use isdisjoint() instead of any() with generator for 5-10x speedup
    if not {"", ".", ".."}.isdisjoint(parts):
        raise ValueError(f"manifest file path contains unsafe segments: {path}")

    return normalized


def _build_agent_ir(req: AgentPackRequest, generated_markdown: str) -> AgentExportIR:
    """Build request-grounded IR even when the optional generator is unavailable.

    Agent packs are downloadable artifacts, so a worker error must never be parsed as
    an agent named ``error``. The generated text can enrich the pack, but the request
    remains the source of truth for project identity, scope, and conservative limits.
    """

    parsed = parse_agent_markdown(generated_markdown or "")
    use_generated = _agent_output_is_usable(parsed, generated_markdown)

    generated_goals = parsed.goals if use_generated else []
    generated_constraints = parsed.constraints if use_generated else []
    generated_workflows = parsed.workflows if use_generated else []
    generated_stack = parsed.tech_stack if use_generated else []

    goals = _unique_lines([req.goal, *generated_goals])
    constraints = _unique_lines(
        [
            *_explicit_goal_constraints(req.goal),
            "Do not invent repository files, commands, APIs, or test results; verify them from the repository.",
            (
                "Treat secrets, production data, destructive operations, dependency changes, pushes, and deploys "
                "as approval-gated."
                if req.risk_mode == "strict"
                else "Prefer the smallest reversible change and preserve behavior outside the stated goal."
            ),
            *generated_constraints,
        ]
    )
    workflows = _unique_lines(
        [
            f"Read repository instructions and inspect the files relevant to this goal: {req.goal}",
            (
                f"Map the existing implementation and tests before editing; treat {req.stack} as declared context, "
                "not proof of repository commands or APIs."
            ),
            _pack_specific_workflow(req.pack_type),
            _validation_workflow(req),
            *generated_workflows,
        ]
    )
    tech_stack = _unique_lines([req.stack, *generated_stack])

    rendered = _render_agent_markdown(
        name=_agent_name(req),
        role=_agent_role(req),
        goals=goals,
        constraints=constraints,
        workflows=workflows,
        tech_stack=tech_stack,
    )
    grounded = parse_agent_markdown(rendered)
    grounded.detected_commands = req.detected_commands or {}
    if req.risk_mode == "strict":
        grounded.permission_mode = "default"  # ask before edits, vs "acceptEdits"
        grounded.strict_permissions = True
    if req.pack_type == "pr-reviewer":
        grounded.allowed_tools = ["Read", "Glob", "Grep", "Bash"]
    return grounded


def _build_skill_ir(req: AgentPackRequest, generated_markdown: str) -> SkillExportIR:
    parsed = parse_skill_markdown(generated_markdown or "")
    use_generated = _skill_output_is_usable(parsed, generated_markdown)

    purpose_parts = [
        req.goal.rstrip("."),
        f"Project: {req.project_type}",
        f"Declared stack: {req.stack}",
    ]
    if use_generated and parsed.purpose:
        purpose_parts.append(parsed.purpose.rstrip("."))

    return SkillExportIR(
        name=parsed.name if use_generated else _tool_name_from_goal(req.goal),
        purpose=". ".join(_unique_lines(purpose_parts)) + ".",
        when_to_use=(
            parsed.when_to_use
            if use_generated and parsed.when_to_use
            else f"Use for the stated {req.project_type} workflow after reviewing repository-specific contracts."
        ),
        params=(
            parsed.params
            if use_generated and parsed.params
            else [
                SkillParam(
                    name="request",
                    type="str",
                    description="The concrete, repository-grounded operation to perform.",
                )
            ]
        ),
        output_type=parsed.output_type if use_generated else "str",
        output_description=(
            parsed.output_description
            if use_generated and parsed.output_description
            else "A reviewable result for the stated goal, including limitations and unresolved TODOs."
        ),
        dependencies=parsed.dependencies if use_generated else [],
        error_handling=_unique_lines(
            [
                "Reject an empty request.",
                "Return a clear error when required repository context is unavailable; do not invent data.",
                *(parsed.error_handling if use_generated else []),
            ]
        ),
        testing_strategy=_unique_lines(
            [
                "Verify one valid request and one missing-context failure without network side effects.",
                *(parsed.testing_strategy if use_generated else []),
            ]
        ),
        performance_notes=parsed.performance_notes if use_generated else [],
        examples=parsed.examples if use_generated else [],
        implementation=(
            parsed.implementation
            if use_generated and parsed.implementation
            else (
                "Validate the request. Resolve repository-specific clients and contracts from the host project. "
                "Perform the read-only operation described by the goal. Return a structured, reviewable result. "
                "Keep unknown integration details as TODOs."
            )
        ),
        raw_definition=generated_markdown.strip() if use_generated else "",
    )


def _agent_output_is_usable(ir: AgentExportIR, markdown: str) -> bool:
    lowered = (markdown or "").strip().lower()
    if not lowered or "failed to generate" in lowered or "api key is missing" in lowered:
        return False
    if ir.name.strip().lower() in {"error", "ai agent"}:
        return False
    return bool(ir.role or ir.goals or ir.constraints or ir.workflows)


def _skill_output_is_usable(ir: SkillExportIR, markdown: str) -> bool:
    lowered = (markdown or "").strip().lower()
    if not lowered or "failed to generate" in lowered or "api key is missing" in lowered:
        return False
    if ir.name.strip().lower() in {"error", "skill_name"}:
        return False
    return bool(ir.purpose or ir.params or ir.implementation)


def _agent_name(req: AgentPackRequest) -> str:
    suffix = {
        "project-pack": "Maintainer",
        "subagent": "Focused Agent",
        "pr-reviewer": "PR Reviewer",
        "mcp-tool-stub": "Tool",
    }[req.pack_type]
    return f"{req.project_type} {suffix}"


def _agent_role(req: AgentPackRequest) -> str:
    if req.pack_type == "pr-reviewer":
        return (
            f"You are a read-only pull request reviewer for {req.project_type}. "
            f"The declared technology context is {req.stack}."
        )
    if req.pack_type == "subagent":
        return (
            f"You are a focused Claude Code subagent for {req.project_type}. "
            f"The declared technology context is {req.stack}."
        )
    return (
        f"You maintain {req.project_type} while staying inside the requested scope. "
        f"The declared technology context is {req.stack}."
    )


def _pack_specific_workflow(pack_type: PackType) -> str:
    if pack_type == "pr-reviewer":
        return (
            "Review the diff and nearby tests without editing; report only actionable findings with file evidence, "
            "then state whether the change is safe to merge."
        )
    if pack_type == "subagent":
        return (
            "Confirm the requested outcome and boundaries, then make or recommend only the smallest evidence-backed "
            "change needed for that outcome."
        )
    return (
        "Confirm the requested outcome and boundaries, implement the smallest scoped change, and keep unrelated "
        "product flows untouched."
    )


def _explicit_goal_constraints(goal: str) -> list[str]:
    constraints: list[str] = []
    for marker in ("without ", "never ", "do not ", "before "):
        index = goal.lower().find(marker)
        if index >= 0:
            clause = goal[index:].strip().rstrip(".")
            if clause:
                constraints.append(clause[0].upper() + clause[1:])
    return constraints


def _render_agent_markdown(
    *,
    name: str,
    role: str,
    goals: list[str],
    constraints: list[str],
    workflows: list[str],
    tech_stack: list[str],
) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    return (
        f"# {name}\n\n"
        f"## Role\n{role}\n\n"
        f"## Goals\n{bullets(goals)}\n\n"
        f"## Constraints\n{bullets(constraints)}\n\n"
        f"## Workflows\n{bullets(workflows)}\n\n"
        f"## Tech Stack\n{bullets(tech_stack)}"
    )


def _tool_name_from_goal(goal: str) -> str:
    first_clause = re.split(r"\band\b|[.;]", goal, maxsplit=1, flags=re.IGNORECASE)[0]
    words = re.findall(r"[a-z0-9]+", first_clause.lower())
    stop_words = {"a", "an", "the", "one", "to", "for", "with", "scoped"}
    meaningful = [word for word in words if word not in stop_words][:4]
    return "_".join(meaningful) or "repository_task"


def _unique_lines(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join((value or "").split()).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
