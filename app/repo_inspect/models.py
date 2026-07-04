from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class RepoFacts(BaseModel):
    """Raw repository facts collected client-side (contents only; no paths read here)."""

    files: dict[str, str] = Field(default_factory=dict)  # repo-relative path -> content
    tree: list[str] = Field(default_factory=list)  # shallow list of top-level entries
    has_claude_md: bool = False
    has_claude_dir: bool = False


@dataclass(frozen=True)
class DetectedCommand:
    name: str  # "test" | "build" | "lint" | "dev" | "format"
    command: str  # e.g. "npm run test", "python -m pytest tests/ -q"
    source: str  # e.g. "web/package.json", "Makefile"


@dataclass(frozen=True)
class StackInfo:
    language: str  # "python" | "javascript" | "go" | "rust" | ...
    frameworks: tuple[str, ...] = ()


@dataclass
class RepoContext:
    stacks: list[StackInfo] = field(default_factory=list)
    commands: list[DetectedCommand] = field(default_factory=list)
    has_existing_claude_md: bool = False
    has_existing_claude_dir: bool = False
    tree: list[str] = field(default_factory=list)

    def command_map(self) -> dict[str, str]:
        """First detected command per name, for templating."""
        out: dict[str, str] = {}
        for c in self.commands:
            out.setdefault(c.name, c.command)
        return out

    def stack_summary(self) -> str:
        langs = ", ".join(sorted({s.language for s in self.stacks}))
        fws = ", ".join(sorted({f for s in self.stacks for f in s.frameworks}))
        return " / ".join(p for p in (langs, fws) if p)
