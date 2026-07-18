"""Read-only local repository enrichment for PR Safety.

Filesystem access stays in this adapter. The analyzer receives only the
normalized :class:`RepoSignalsSection`, keeping verdict logic deterministic
and reusable by future GitHub-backed adapters.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from app.pr_safety.models import (
    RepoCommandSignal,
    RepoOwnerMatch,
    RepoSignalsSection,
    RepoStackSignal,
    RepoWorkflowSignal,
)
from app.pr_safety.path_rules import normalize_paths
from app.repo_inspect import RepoFacts, derive_repo_context

_CODEOWNERS_LOCATIONS = (
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
)
_MANIFEST_NAMES = {
    "Makefile",
    "makefile",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "Gemfile",
}
_IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
    "vendor",
}
_MAX_SCAN_DEPTH = 2
_MAX_FILE_BYTES = 256_000


def collect_repo_signals(repo_root: Path, changed_files: list[str]) -> RepoSignalsSection:
    """Collect bounded, advisory repository facts from a trusted local checkout."""
    root = repo_root.resolve()
    warnings: list[str] = []
    files = [path for path in normalize_paths(changed_files) if _is_safe_relative_path(path)]

    facts = _collect_repo_facts(root, warnings)
    context = derive_repo_context(facts)

    return RepoSignalsSection(
        source="local_checkout",
        owners=_collect_owner_matches(root, files, warnings),
        overlapping_workflows=_collect_workflow_matches(root, files, warnings),
        detected_commands=[
            RepoCommandSignal(name=item.name, command=item.command, source=item.source)
            for item in sorted(context.commands, key=lambda item: (item.name, item.source))
        ],
        stacks=[
            RepoStackSignal(language=item.language, frameworks=list(item.frameworks))
            for item in sorted(context.stacks, key=lambda item: item.language)
        ],
        warnings=warnings,
    )


def _is_safe_relative_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _collect_repo_facts(root: Path, warnings: list[str]) -> RepoFacts:
    contents: dict[str, str] = {}
    for path in _manifest_paths(root):
        relative = path.relative_to(root).as_posix()
        content = _read_bounded_text(root, path, relative, warnings)
        if content is not None:
            contents[relative] = content

    try:
        tree = sorted(path.name for path in root.iterdir())
    except OSError:
        tree = []
        warnings.append("Could not list repository root")

    return RepoFacts(
        files=contents,
        tree=tree,
        has_claude_md=(root / "CLAUDE.md").is_file(),
        has_claude_dir=(root / ".claude").is_dir(),
    )


def _manifest_paths(root: Path) -> list[Path]:
    matches: list[Path] = []
    for current, directories, filenames in os.walk(root):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue

        directories[:] = sorted(
            name
            for name in directories
            if name not in _IGNORED_DIRECTORIES and not name.startswith(".")
        )
        if depth >= _MAX_SCAN_DEPTH:
            directories[:] = []

        for filename in sorted(filenames):
            if filename in _MANIFEST_NAMES:
                matches.append(current_path / filename)
    return sorted(matches, key=lambda path: path.relative_to(root).as_posix())


def _read_bounded_text(
    root: Path,
    path: Path,
    relative: str,
    warnings: list[str],
) -> str | None:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            warnings.append(f"Skipped repository file outside root: {relative}")
            return None
        if resolved.stat().st_size > _MAX_FILE_BYTES:
            warnings.append(f"Skipped oversized repository file: {relative}")
            return None
        return resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        warnings.append(f"Could not read repository file: {relative}")
        return None


def _collect_owner_matches(
    root: Path,
    changed_files: list[str],
    warnings: list[str],
) -> list[RepoOwnerMatch]:
    source = next(
        (location for location in _CODEOWNERS_LOCATIONS if (root / location).is_file()), None
    )
    if source is None:
        return []

    content = _read_bounded_text(root, root / source, source, warnings)
    if content is None:
        return []

    rules: list[tuple[str, list[str]]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        try:
            parts = shlex.split(line, comments=True, posix=True)
        except ValueError:
            warnings.append(f"Ignored malformed CODEOWNERS line {line_number} in {source}")
            continue
        if len(parts) < 2:
            continue
        pattern, *owners = parts
        if pattern.startswith("!"):
            warnings.append(
                f"Ignored unsupported CODEOWNERS pattern on line {line_number} in {source}"
            )
            continue
        owners = [owner for owner in owners if _looks_like_owner(owner)]
        if owners:
            rules.append((pattern, owners))

    matches: list[RepoOwnerMatch] = []
    for changed_file in changed_files:
        selected: tuple[str, list[str]] | None = None
        for pattern, owners in rules:
            if _matches_repo_pattern(changed_file, pattern):
                selected = (pattern, owners)
        if selected is not None:
            pattern, owners = selected
            matches.append(
                RepoOwnerMatch(
                    file=changed_file,
                    owners=owners,
                    pattern=pattern,
                    source=source,
                )
            )
    return matches


def _looks_like_owner(value: str) -> bool:
    return value.startswith("@") or ("@" in value and not any(char.isspace() for char in value))


def _collect_workflow_matches(
    root: Path,
    changed_files: list[str],
    warnings: list[str],
) -> list[RepoWorkflowSignal]:
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return []

    matches: list[RepoWorkflowSignal] = []
    workflow_paths = sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])
    for path in workflow_paths:
        relative = path.relative_to(root).as_posix()
        content = _read_bounded_text(root, path, relative, warnings)
        if content is None:
            continue
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            warnings.append(f"Could not parse GitHub workflow: {relative}")
            continue
        if not isinstance(data, dict):
            warnings.append(f"Could not parse GitHub workflow: {relative}")
            continue

        pull_request_config = _pull_request_config(data)
        if pull_request_config is None:
            continue

        matched_files = _workflow_matched_files(changed_files, pull_request_config)
        if not matched_files:
            continue

        raw_jobs = data.get("jobs")
        jobs = sorted(str(name) for name in raw_jobs) if isinstance(raw_jobs, dict) else []
        raw_name = data.get("name")
        name = _single_line(raw_name) if isinstance(raw_name, str) else path.stem
        matches.append(
            RepoWorkflowSignal(
                path=relative,
                name=name,
                jobs=jobs,
                matched_files=matched_files,
            )
        )
    return matches


def _pull_request_config(workflow: dict[Any, Any]) -> dict[str, Any] | None:
    trigger = workflow.get("on", workflow.get(True))
    if isinstance(trigger, str):
        return {} if trigger == "pull_request" else None
    if isinstance(trigger, list):
        return {} if "pull_request" in trigger else None
    if not isinstance(trigger, dict) or "pull_request" not in trigger:
        return None
    config = trigger.get("pull_request")
    return config if isinstance(config, dict) else {}


def _workflow_matched_files(
    changed_files: list[str],
    config: dict[str, Any],
) -> list[str]:
    include = _string_list(config.get("paths"))
    exclude = _string_list(config.get("paths-ignore"))

    matched = [
        path
        for path in changed_files
        if (not include or _matches_ordered_patterns(path, include))
        and not _matches_any_repo_pattern(path, exclude)
    ]
    return matched


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _matches_ordered_patterns(path: str, patterns: list[str]) -> bool:
    included = False
    for raw_pattern in patterns:
        negated = raw_pattern.startswith("!")
        pattern = raw_pattern[1:] if negated else raw_pattern
        if _matches_repo_pattern(path, pattern):
            included = not negated
    return included


def _matches_any_repo_pattern(path: str, patterns: list[str]) -> bool:
    return any(_matches_repo_pattern(path, pattern) for pattern in patterns)


def _matches_repo_pattern(path: str, raw_pattern: str) -> bool:
    pattern = raw_pattern.strip().replace("\\", "/")
    if not pattern:
        return False

    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    pattern = pattern.lstrip("/")
    if pattern.endswith("/"):
        pattern += "**"

    prefix = "^" if anchored else r"^(?:.*/)?"
    expression: list[str] = [prefix]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                if index + 2 < len(pattern) and pattern[index + 2] == "/":
                    # GitHub-style `**/` should match zero or more directories,
                    # including files that live at the repository root.
                    expression.append("(?:[^/]+/)*")
                    index += 3
                    continue
                expression.append(".*")
                index += 2
                continue
            expression.append("[^/]*")
        elif char == "?":
            expression.append("[^/]")
        else:
            expression.append(re.escape(char))
        index += 1
    expression.append("$")
    return re.match("".join(expression), path) is not None


def _single_line(value: str) -> str:
    return " ".join(value.split())
