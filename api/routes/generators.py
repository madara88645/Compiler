from __future__ import annotations

import time
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key, verify_api_key_if_required
from api.shared import logger
from app.github_repo_context import (
    GitHubRepoAnalysisError,
    InvalidGitHubRepoUrl,
    analyze_public_github_repo,
)


def _safe_repo_full_name(repo_url: str) -> str | None:
    try:
        parsed = urlparse((repo_url or "").strip())
        if parsed.netloc.lower() != "github.com":
            return None
        segments = [seg for seg in parsed.path.split("/") if seg]
        if len(segments) < 2:
            return None
        return f"{segments[0]}/{segments[1]}"
    except Exception:
        return None


def _log_repo_analyze_outcome(
    *,
    outcome: str,
    repo_url: str,
    started_at: float,
    repo_full_name: str | None = None,
    status_code: int | None = None,
    error_message: str | None = None,
) -> None:
    duration_ms = round((time.monotonic() - started_at) * 1000, 2)
    extra = {
        "event": "repo_analyze",
        "outcome": outcome,
        "repo_full_name": repo_full_name or _safe_repo_full_name(repo_url),
        "duration_ms": duration_ms,
    }
    if status_code is not None:
        extra["status_code"] = status_code
    if error_message:
        extra["error_message"] = error_message
    logger.info("repo_analyze outcome=%s", outcome, extra=extra)


router = APIRouter(tags=["generators"])

_MAX_DESCRIPTION_CHARS = 8_000


def _get_compiler():
    from api import main as api_main

    return api_main.get_compiler()


RepoContextMode = Literal["full", "compact"]


class GitHubRepoContextPayload(BaseModel):
    normalized_repo_url: str = Field(..., min_length=1, max_length=500)
    repo_full_name: str = Field(..., min_length=1, max_length=255)
    requested_ref: str | None = Field(default=None, max_length=255)
    requested_subdir: str | None = Field(default=None, max_length=500)
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
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    started_at = time.monotonic()

    try:
        payload = analyze_public_github_repo(req.repo_url)
    except InvalidGitHubRepoUrl as exc:
        _log_repo_analyze_outcome(
            outcome="invalid_url",
            repo_url=req.repo_url,
            started_at=started_at,
            status_code=400,
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubRepoAnalysisError as exc:
        outcome = "not_found" if exc.status_code == 404 else "upstream_error"
        _log_repo_analyze_outcome(
            outcome=outcome,
            repo_url=req.repo_url,
            started_at=started_at,
            status_code=exc.status_code,
            error_message=str(exc),
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("github repo analysis failed")
        _log_repo_analyze_outcome(
            outcome="internal_error",
            repo_url=req.repo_url,
            started_at=started_at,
            status_code=500,
            error_message=str(exc),
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc

    _log_repo_analyze_outcome(
        outcome="ok",
        repo_url=req.repo_url,
        started_at=started_at,
        repo_full_name=payload.get("repo_full_name") if isinstance(payload, dict) else None,
        status_code=200,
    )
    return GitHubRepoContextPayload.model_validate(payload)


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
