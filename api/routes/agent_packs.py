from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import rate_limit_by_ip

from api.shared import _get_compiler, logger
from pydantic import BaseModel

from app.adapters.agent_packs import (
    AGENT_PACK_ADAPTERS,
    AgentPackManifest,
    AgentPackRequest,
    create_download_response,
)
from app.repo_inspect import RepoFacts, derive_repo_context
from app.repo_inspect.claude_md_merge import merge_claude_md

router = APIRouter(tags=["agent-packs"])


@router.post("/agent-packs/claude", response_model=AgentPackManifest)
async def build_claude_agent_pack(
    req: AgentPackRequest,
    _: None = Depends(rate_limit_by_ip),
):
    compiler = _get_compiler()
    adapter = AGENT_PACK_ADAPTERS["claude"]

    try:
        return adapter.build_manifest(req, compiler)
    except Exception as exc:
        logger.exception(
            "agent pack generation failed", extra={"provider": "claude", "pack_type": req.pack_type}
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/agent-packs/claude/download")
async def download_claude_agent_pack(
    req: AgentPackRequest,
    _: None = Depends(rate_limit_by_ip),
):
    compiler = _get_compiler()
    adapter = AGENT_PACK_ADAPTERS["claude"]

    try:
        manifest = adapter.build_manifest(req, compiler)
        return create_download_response(manifest)
    except Exception as exc:
        logger.exception(
            "agent pack download failed", extra={"provider": "claude", "pack_type": req.pack_type}
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


class RepoPlanRequest(BaseModel):
    pack_type: str
    goal: str
    risk_mode: str = "balanced"
    project_type: str = "repository"
    repo_facts: RepoFacts


def _diff_action(existing: dict[str, str], path: str, content: str) -> str:
    if path not in existing:
        return "create"
    return "identical" if existing[path] == content else "overwrite"


@router.post("/agent-packs/claude/repo-plan")
async def repo_plan_claude_agent_pack(
    req: RepoPlanRequest,
    _: None = Depends(rate_limit_by_ip),
):
    """Generate a repo-aware Claude pack and diff it against the client's existing files.

    Pure: derives context from the supplied repo facts, generates the manifest, and returns
    the file plan (create/overwrite/identical). Never touches the filesystem — the MCP client
    owns all local I/O.
    """
    compiler = _get_compiler()
    adapter = AGENT_PACK_ADAPTERS["claude"]
    try:
        ctx = derive_repo_context(req.repo_facts)
        pack_req = AgentPackRequest(
            project_type=req.project_type,
            stack=ctx.stack_summary() or "unspecified",
            goal=req.goal,
            pack_type=req.pack_type,
            risk_mode=req.risk_mode,
            detected_commands=ctx.command_map() or None,
            detected_stack=ctx.stack_summary() or None,
            has_existing_claude_md=ctx.has_existing_claude_md,
        )
        manifest = adapter.build_manifest(pack_req, compiler)
    except Exception as exc:
        logger.exception(
            "agent pack repo-plan failed",
            extra={"provider": "claude", "pack_type": req.pack_type},
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc

    existing = req.repo_facts.files
    data = manifest.model_dump()
    plan: list[dict] = []
    for f in data["files"]:
        path, content = f["path"], f["content"]
        if path == "CLAUDE.md" and "CLAUDE.md" in existing:
            merged = merge_claude_md(existing["CLAUDE.md"], content)
            f["content"] = merged
            plan.append(
                {
                    "path": path,
                    "action": "identical" if merged == existing["CLAUDE.md"] else "merge",
                }
            )
        else:
            plan.append({"path": path, "action": _diff_action(existing, path, content)})
    return {
        "manifest": data,
        "plan": plan,
        "detected": {
            "stack": ctx.stack_summary(),
            "commands": ctx.command_map(),
            "has_existing_claude_md": ctx.has_existing_claude_md,
        },
    }
