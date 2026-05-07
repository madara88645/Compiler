from __future__ import annotations

import io
from typing import Any, Literal, Protocol
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.responses import Response
from pydantic import BaseModel, Field

from .agent_ir import parse_agent_markdown
from .claude_code import (
    to_claude_mcp_tool_stub,
    to_claude_pr_reviewer_pack,
    to_claude_project_pack,
    to_claude_subagent_bundle,
)
from .skill_ir import parse_skill_markdown

PackType = Literal["project-pack", "subagent", "pr-reviewer", "mcp-tool-stub"]
RiskMode = Literal["balanced", "strict"]


class AgentPackRequest(BaseModel):
    project_type: str = Field(..., min_length=1, max_length=120)
    stack: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=8_000)
    pack_type: PackType
    risk_mode: RiskMode = "balanced"


class AgentPackFile(BaseModel):
    path: str
    content: str
    kind: str


class AgentPackManifest(BaseModel):
    provider: str
    pack_type: PackType
    files: list[AgentPackFile]
    download_name: str
    preview_order: list[str]


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
            skill_ir = parse_skill_markdown(skill_definition)
            raw_files = to_claude_mcp_tool_stub(skill_ir)
        else:
            system_prompt = compiler.generate_agent(
                _build_agent_brief(req),
                multi_agent=False,
                include_example_code=False,
            )
            agent_ir = parse_agent_markdown(system_prompt)

            if req.pack_type == "project-pack":
                raw_files = to_claude_project_pack(agent_ir)
            elif req.pack_type == "subagent":
                raw_files = to_claude_subagent_bundle(agent_ir)
            else:
                raw_files = to_claude_pr_reviewer_pack(agent_ir)

        files = [
            AgentPackFile(
                path=file["path"], content=file["content"], kind=_classify_kind(file["path"])
            )
            for file in raw_files
        ]
        preview_order = [
            kind for kind in _preview_order() if any(file.kind == kind for file in files)
        ]
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
        f"Stack: {req.stack}\n"
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


def _classify_kind(path: str) -> str:
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


def _preview_order() -> list[str]:
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
