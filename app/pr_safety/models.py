from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PrSafetyVerdict = Literal["merge", "hold", "split", "rebase"]

SignalStatus = Literal["ok", "gap", "mismatch", "stale", "unknown", "hit"]


class FileGroup(BaseModel):
    name: str
    files: list[str] = Field(default_factory=list)


class ChangedFilesSection(BaseModel):
    total: int = 0
    groups: list[FileGroup] = Field(default_factory=list)


class RiskyAreaHit(BaseModel):
    category: str
    file: str
    reason: str


class RiskyAreasSection(BaseModel):
    hits: list[RiskyAreaHit] = Field(default_factory=list)
    status: SignalStatus = "ok"


class TestGapSignal(BaseModel):
    file: str
    reason: str


class TestCoverageSection(BaseModel):
    status: SignalStatus = "ok"
    gaps: list[TestGapSignal] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)


class BranchFreshnessSection(BaseModel):
    status: SignalStatus = "unknown"
    commits_behind: int | None = None
    notes: list[str] = Field(default_factory=list)


class ScopeMatchSection(BaseModel):
    status: SignalStatus = "ok"
    notes: list[str] = Field(default_factory=list)


class PrSafetyReport(BaseModel):
    verdict: PrSafetyVerdict
    title: str
    changed_files: ChangedFilesSection
    risky_areas: RiskyAreasSection
    test_coverage: TestCoverageSection
    branch_freshness: BranchFreshnessSection
    scope_match: ScopeMatchSection
    recommendations: list[str] = Field(default_factory=list)
