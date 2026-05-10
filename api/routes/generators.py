from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key
from api.shared import logger
from app.github_repo_context import (
    GitHubRepoAnalysisError,
    InvalidGitHubRepoUrl,
    analyze_public_github_repo,
)

router = APIRouter(tags=["generators"])

_MAX_DESCRIPTION_CHARS = 8_000


def _get_compiler():
    from api import main as api_main

    return api_main.get_compiler()


RepoContextMode = Literal["full", "compact"]


class GitHubRepoContextPayload(BaseModel):
    normalized_repo_url: str = Field(..., min_length=1, max_length=500)
    repo_full_name: str = Field(..., min_length=1, max_length=255)
    default_branch: str | None = Field(default=None, max_length=255)
    summary: str = Field(..., min_length=1, max_length=1_500)
    summary_compact: str | None = Field(default=None, max_length=400)
    highlights: list[str] = Field(default_factory=list, max_length=6)
    files_used: list[str] = Field(default_factory=list, max_length=6)
    detected_stack: list[str] = Field(default_factory=list, max_length=6)


class GitHubRepoContextRequest(BaseModel):
    repo_url: str = Field(..., min_length=1, max_length=500)


class SkillGenRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    include_example_code: bool = Field(
        default=False,
        description="Whether generated skill definition should include implementation example code",
    )
    repo_context: GitHubRepoContextPayload | None = None
    repo_context_mode: RepoContextMode = Field(
        default="full",
        description="Whether to use the full or the compact repo brief in the generator prompt.",
    )


class SkillGenResponse(BaseModel):
    skill_definition: str


class AgentGenRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    multi_agent: bool = Field(default=False, description="Generate a multi-agent swarm if true")
    include_example_code: bool = Field(default=False, description="Include pseudo-code example")
    repo_context: GitHubRepoContextPayload | None = None
    repo_context_mode: RepoContextMode = Field(
        default="full",
        description="Whether to use the full or the compact repo brief in the generator prompt.",
    )


class AgentGenResponse(BaseModel):
    system_prompt: str


@router.post("/repo-context/github", response_model=GitHubRepoContextPayload)
async def analyze_github_repo_endpoint(
    req: GitHubRepoContextRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key

    try:
        return GitHubRepoContextPayload.model_validate(analyze_public_github_repo(req.repo_url))
    except InvalidGitHubRepoUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubRepoAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("github repo analysis failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/skills-generator/generate", response_model=SkillGenResponse)
async def generate_skill_endpoint(
    req: SkillGenRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    compiler = _get_compiler()

    try:
        result = compiler.generate_skill(
            req.description,
            include_example_code=req.include_example_code,
            repo_context=req.repo_context.model_dump() if req.repo_context else None,
            repo_context_mode=req.repo_context_mode,
        )
        return SkillGenResponse(skill_definition=result)
    except Exception as exc:
        logger.exception("skill generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/agent-generator/generate", response_model=AgentGenResponse)
async def generate_agent_endpoint(
    req: AgentGenRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    compiler = _get_compiler()

    try:
        result = compiler.generate_agent(
            req.description,
            multi_agent=req.multi_agent,
            include_example_code=req.include_example_code,
            repo_context=req.repo_context.model_dump() if req.repo_context else None,
            repo_context_mode=req.repo_context_mode,
        )
        return AgentGenResponse(system_prompt=result)
    except Exception as exc:
        logger.exception("agent generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
