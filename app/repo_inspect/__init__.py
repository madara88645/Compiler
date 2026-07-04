from __future__ import annotations

from .detect import detect_stacks, parse_makefile_targets, parse_package_json_scripts
from .models import DetectedCommand, RepoContext, RepoFacts, StackInfo

__all__ = ["RepoFacts", "RepoContext", "DetectedCommand", "StackInfo", "derive_repo_context"]

# Precedence: a Makefile 'test' target beats a package.json 'test' script, etc.
_SOURCE_PRIORITY = ("Makefile", "makefile", "pyproject.toml", "package.json")


def _source_rank(source: str) -> int:
    for i, needle in enumerate(_SOURCE_PRIORITY):
        if source.endswith(needle):
            return i
    return len(_SOURCE_PRIORITY)


def derive_repo_context(facts: RepoFacts) -> RepoContext:
    commands: list[DetectedCommand] = []
    for path, content in facts.files.items():
        base = path.rsplit("/", 1)[-1]
        if base == "package.json":
            commands += parse_package_json_scripts(content, path)
        elif base in ("Makefile", "makefile"):
            commands += parse_makefile_targets(content, path)

    # Keep the highest-priority command per name.
    best: dict[str, DetectedCommand] = {}
    for c in sorted(commands, key=lambda c: _source_rank(c.source)):
        best.setdefault(c.name, c)

    return RepoContext(
        stacks=detect_stacks(facts.files),
        commands=list(best.values()),
        has_existing_claude_md=facts.has_claude_md,
        has_existing_claude_dir=facts.has_claude_dir,
        tree=list(facts.tree),
    )
