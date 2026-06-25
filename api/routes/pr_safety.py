from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import rate_limit_by_ip
from app.pr_safety.analyzer import analyze_pr_safety
from app.pr_safety.models import PrSafetyReport
from app.repo_context import RepoContextInput, RepoContextMode

router = APIRouter(tags=["pr-safety"])


class PrSafetyReportRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Pull request title")
    description: str = Field(..., min_length=1, description="Pull request description or body")
    changed_files: list[str] = Field(
        ...,
        min_length=1,
        description="Changed file paths, one entry per path",
    )
    commits_behind: int | None = Field(
        default=None,
        ge=0,
        description="Optional number of commits the branch is behind the base branch",
    )
    repo_context: RepoContextInput | None = Field(
        default=None,
        description="Reserved optional repo context for future repo-aware PR Safety checks.",
    )
    repo_context_mode: RepoContextMode = Field(
        default="compact",
        description="Reserved repo context rendering mode for future repo-aware PR Safety checks.",
    )


@router.post("/pr-safety/report", response_model=PrSafetyReport)
async def create_pr_safety_report(
    req: PrSafetyReportRequest,
    _: None = Depends(rate_limit_by_ip),
) -> PrSafetyReport:
    return analyze_pr_safety(
        req.title,
        req.description,
        req.changed_files,
        commits_behind=req.commits_behind,
    )
