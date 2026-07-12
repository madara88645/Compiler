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


class RepoOwnerMatch(BaseModel):
    file: str
    owners: list[str] = Field(default_factory=list)
    pattern: str
    source: str


class RepoWorkflowSignal(BaseModel):
    path: str
    name: str
    jobs: list[str] = Field(default_factory=list)
    matched_files: list[str] = Field(default_factory=list)


class RepoCommandSignal(BaseModel):
    name: str
    command: str
    source: str


class RepoStackSignal(BaseModel):
    language: str
    frameworks: list[str] = Field(default_factory=list)


class RepoSignalsSection(BaseModel):
    """Advisory repository facts collected outside the pure analyzer."""

    source: str = "local_checkout"
    owners: list[RepoOwnerMatch] = Field(default_factory=list)
    overlapping_workflows: list[RepoWorkflowSignal] = Field(default_factory=list)
    detected_commands: list[RepoCommandSignal] = Field(default_factory=list)
    stacks: list[RepoStackSignal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PrSafetyReport(BaseModel):
    verdict: PrSafetyVerdict
    title: str
    changed_files: ChangedFilesSection
    risky_areas: RiskyAreasSection
    test_coverage: TestCoverageSection
    branch_freshness: BranchFreshnessSection
    scope_match: ScopeMatchSection
    recommendations: list[str] = Field(default_factory=list)


class RepoAwarePrSafetyReport(PrSafetyReport):
    """PR Safety report enriched by an explicit repository-signal adapter."""

    repo_signals: RepoSignalsSection
