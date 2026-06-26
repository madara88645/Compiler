from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

RepoContextSource: TypeAlias = Literal["github_public", "rag_index", "local_upload", "manual"]
RepoContextMode: TypeAlias = Literal["full", "compact"]


class RepoContextIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, max_length=255)
    ref: str | None = Field(default=None, max_length=255)


class RepoContextSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full: str = Field(default="", max_length=1_500)
    compact: str | None = Field(default=None, max_length=400)


class RepoContextSnippet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_path: str = Field(..., min_length=1, max_length=240)
    content: str = Field(default="", max_length=2_000)
    score: float | None = None
    source_label: str | None = Field(default=None, max_length=120)


class RepoContextBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_chars: int = Field(default=4_000, ge=200, le=20_000)
    used_chars: int = Field(default=0, ge=0, le=20_000)
    truncated: bool = False


class RepoContextSafety(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path_safe: bool = True
    contains_absolute_paths: bool = False


class RepoContextEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_type: RepoContextSource
    repo_identity: RepoContextIdentity = Field(default_factory=RepoContextIdentity)
    summary: RepoContextSummary = Field(default_factory=RepoContextSummary)
    detected_stack: list[str] = Field(default_factory=list, max_length=12)
    files_used: list[str] = Field(default_factory=list, max_length=24)
    snippets: list[RepoContextSnippet] = Field(default_factory=list, max_length=12)
    budget: RepoContextBudget = Field(default_factory=RepoContextBudget)
    safety: RepoContextSafety = Field(default_factory=RepoContextSafety)

    @field_validator("detected_stack", "files_used", mode="after")
    @classmethod
    def validate_short_list_items(cls, items: list[str]) -> list[str]:
        return [str(item).strip()[:240] for item in items if str(item).strip()]


class GitHubRepoContextPayload(BaseModel):
    """Backward-compatible public payload for /repo-context/github and generator requests."""

    model_config = ConfigDict(extra="ignore")

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

    @field_validator("highlights", "files_used", "detected_stack", mode="after")
    @classmethod
    def validate_list_items_length(cls, items: list[str]) -> list[str]:
        for item in items:
            if len(item) > 1024:
                raise ValueError("Item in list exceeds maximum length of 1024 characters")
        return items


RepoContextInput: TypeAlias = RepoContextEnvelope | GitHubRepoContextPayload
