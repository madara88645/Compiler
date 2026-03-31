from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key_if_required
from api.shared import logger

router = APIRouter(tags=["generators"])

_MAX_DESCRIPTION_CHARS = 8_000


def _get_compiler():
    from api import main as api_main

    return api_main.get_compiler()


class SkillGenRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    include_example_code: bool = Field(
        default=False,
        description="Whether generated skill definition should include implementation example code",
    )


class SkillGenResponse(BaseModel):
    skill_definition: str


class AgentGenRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    multi_agent: bool = Field(default=False, description="Generate a multi-agent swarm if true")
    include_example_code: bool = Field(default=False, description="Include pseudo-code example")


class AgentGenResponse(BaseModel):
    system_prompt: str


@router.post("/skills-generator/generate", response_model=SkillGenResponse)
async def generate_skill_endpoint(
    req: SkillGenRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    compiler = _get_compiler()

    try:
        result = compiler.generate_skill(
            req.description,
            include_example_code=req.include_example_code,
        )
        return SkillGenResponse(skill_definition=result)
    except Exception as exc:
        logger.exception("skill generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/agent-generator/generate", response_model=AgentGenResponse)
async def generate_agent_endpoint(
    req: AgentGenRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    compiler = _get_compiler()

    try:
        result = compiler.generate_agent(
            req.description,
            multi_agent=req.multi_agent,
            include_example_code=req.include_example_code,
        )
        return AgentGenResponse(system_prompt=result)
    except Exception as exc:
        logger.exception("agent generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
