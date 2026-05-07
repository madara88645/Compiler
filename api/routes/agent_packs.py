from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import APIKey, verify_api_key
from api.shared import logger
from app.adapters.agent_packs import (
    AGENT_PACK_ADAPTERS,
    AgentPackManifest,
    AgentPackRequest,
    create_download_response,
)

router = APIRouter(tags=["agent-packs"])


def _get_compiler():
    from api import main as api_main

    return api_main.get_compiler()


@router.post("/agent-packs/claude", response_model=AgentPackManifest)
async def build_claude_agent_pack(
    req: AgentPackRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
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
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
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
