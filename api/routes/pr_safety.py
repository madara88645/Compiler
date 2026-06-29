from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import rate_limit_by_ip
from app.pr_safety.analyzer import analyze_pr_safety
from app.pr_safety.markdown import report_to_markdown
from app.pr_safety.models import PrSafetyReport

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


class PrSafetyExportResponse(BaseModel):
    markdown: str
    json_payload: dict = Field(serialization_alias="json")
    filename: str


def _build_pr_safety_report(req: PrSafetyReportRequest) -> PrSafetyReport:
    return analyze_pr_safety(
        req.title,
        req.description,
        req.changed_files,
        commits_behind=req.commits_behind,
    )


@router.post("/pr-safety/report", response_model=PrSafetyReport)
async def create_pr_safety_report(
    req: PrSafetyReportRequest,
    _: None = Depends(rate_limit_by_ip),
) -> PrSafetyReport:
    return _build_pr_safety_report(req)


@router.post("/pr-safety/report/export", response_model=PrSafetyExportResponse)
async def export_pr_safety_report(
    req: PrSafetyReportRequest,
    _: None = Depends(rate_limit_by_ip),
) -> PrSafetyExportResponse:
    report = _build_pr_safety_report(req)
    return PrSafetyExportResponse(
        markdown=report_to_markdown(report),
        json_payload=report.model_dump(mode="json"),
        filename="pr-safety-report.md",
    )
