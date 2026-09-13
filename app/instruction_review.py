"""Deterministic, report-only review of pasted instruction files.

This module deliberately accepts text and names only. It does not resolve paths,
read a checkout, call a model, or write an edited file. The suggested text is a
conservative same-section cleanup for exact duplicate prose rules.
"""

from __future__ import annotations

import difflib
import os
import posixpath
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_FILES = 12
MAX_FILE_CHARS = 120_000
MAX_TOTAL_CHARS = 120_000
MAX_PATH_CHARS = 240
MAX_KNOWN_REPO_FILES = 10_000
MAX_KNOWN_REPO_CHARS = 600_000
MAX_CONFLICT_FINDINGS = 256
MAX_CONFLICT_RELATED = 8


def _configured_limit(name: str, default: int) -> int:
    """Read a small deployment limit without allowing it above the safe default."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return min(max(value, 1), default)


def _validate_relative_name(value: str, label: str) -> str:
    """Validate a display name as a relative slash-separated name.

    Pure string checks keep this endpoint from interpreting user input as a
    filesystem path. Backslashes are normalized for stable comparisons, but no
    path is resolved or opened.
    """
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if len(normalized) > MAX_PATH_CHARS:
        raise ValueError(f"{label} exceeds maximum length of {MAX_PATH_CHARS} characters")
    if "\x00" in normalized:
        raise ValueError(f"{label} contains an invalid null character")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(f"{label} contains an invalid control character")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"{label} must be a relative name")

    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} contains an invalid relative segment")
    return normalized


class InstructionFile(BaseModel):
    """One pasted or uploaded instruction document."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., min_length=1, max_length=MAX_PATH_CHARS)
    content: str = Field(default="", max_length=MAX_FILE_CHARS)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_relative_name(value, "file path")


class InstructionReviewRequest(BaseModel):
    """Bounded request model for the public report-only review endpoint."""

    model_config = ConfigDict(extra="forbid")

    files: list[InstructionFile] = Field(..., min_length=1, max_length=MAX_FILES)
    known_repo_files: list[str] | None = Field(default=None, max_length=MAX_KNOWN_REPO_FILES)

    @field_validator("known_repo_files")
    @classmethod
    def validate_known_repo_files(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None

        normalized: list[str] = []
        total_chars = 0
        for value in values:
            name = _validate_relative_name(value, "known repository file")
            normalized.append(name)
            total_chars += len(name)
        if total_chars > MAX_KNOWN_REPO_CHARS:
            raise ValueError(
                f"known_repo_files exceeds maximum aggregate length of {MAX_KNOWN_REPO_CHARS} characters"
            )
        if len(set(normalized)) != len(normalized):
            raise ValueError("known_repo_files must not contain duplicate paths")
        return normalized

    @model_validator(mode="after")
    def validate_bounds_and_paths(self) -> InstructionReviewRequest:
        max_files = _configured_limit("PROMPTC_INSTRUCTION_REVIEW_MAX_FILES", MAX_FILES)
        max_total_chars = _configured_limit(
            "PROMPTC_INSTRUCTION_REVIEW_MAX_TOTAL_CHARS", MAX_TOTAL_CHARS
        )
        if len(self.files) > max_files:
            raise ValueError(f"at most {max_files} instruction files may be reviewed")

        paths = [item.path for item in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("files must not contain duplicate paths")

        total_chars = sum(len(item.content) for item in self.files)
        if total_chars > max_total_chars:
            raise ValueError(
                f"instruction file content exceeds maximum aggregate length of {max_total_chars} characters"
            )
        return self


RelatedKind = Literal["duplicate_rule", "potential_conflict", "stale_link", "context_split"]
FindingSeverity = Literal["info", "warning", "error"]


class RelatedLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    line: int = Field(..., ge=1)


class InstructionReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RelatedKind
    severity: FindingSeverity
    message: str
    path: str
    line: int = Field(..., ge=1)
    related: list[RelatedLocation] = Field(default_factory=list)


class ReviewedInstructionFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    original: str
    suggested: str
    diff: str


class InstructionReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files_reviewed: int = Field(..., ge=0)
    lines_reviewed: int = Field(..., ge=0)
    findings_count: int = Field(..., ge=0)
    duplicate_lines_removed: int = Field(..., ge=0)
    potential_conflicts: int = Field(..., ge=0)
    stale_links: int = Field(..., ge=0)
    context_notes: int = Field(..., ge=0)
    changed_files: int = Field(..., ge=0)
    preserved_lines: int = Field(..., ge=0)


class InstructionReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[InstructionReviewFinding] = Field(default_factory=list)
    files: list[ReviewedInstructionFile] = Field(default_factory=list)
    summary: InstructionReviewSummary


@dataclass(frozen=True)
class _RuleLine:
    path: str
    line_index: int
    line_number: int
    section_key: tuple[tuple[int, str, int], ...]
    canonical: str
    body: str
    conditional: bool
    command: str | None
    negative: bool
    positive: bool
    safe_to_remove: bool


@dataclass(frozen=True)
class _Link:
    path: str
    line_number: int
    target: str


@dataclass(frozen=True)
class _ImportReference:
    path: str
    line_number: int
    target: str


_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_CHECKBOX_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s+", re.IGNORECASE)
_DIRECTIVE_RE = re.compile(
    r"^(?:always|avoid|call|do|enable|ensure|execute|forbid|include|keep|must|never|only|prefer|preserve|require|run|set|should|use)\b",
    re.IGNORECASE,
)
_CONDITION_RE = re.compile(
    r"\b(?:if|when|unless|only if|provided that|except when|as long as)\b|^(?:on|for)\s+[^,]+,",
    re.IGNORECASE,
)
_NEGATIVE_RE = re.compile(
    r"^(?:never|do not|don't|must not|should not|avoid|forbid|disallow|prohibit)\b",
    re.IGNORECASE,
)
_POSITIVE_RE = re.compile(
    r"^(?:always|must|should|run|use|execute|call|allow|enable|include|prefer|keep|set)\b",
    re.IGNORECASE,
)
_COMMAND_RE = re.compile(
    r"(?<![\w-])(?:pytest|npm|pnpm|yarn|bun|uv|pip|python|python3|node|npx|ruff|git|make|docker|podman|fly|curl|go|cargo|mix|gradle|mvn)\b[^\n,.;)]*",
    re.IGNORECASE,
)
_INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))", re.IGNORECASE)
_REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))", re.IGNORECASE)
_IMPORT_RE = re.compile(
    r"^\s*(?:@\s*(?P<at>[^\s]+\.md)|(?:include|import)\s+(?P<word>[^\s]+\.md))\s*$", re.IGNORECASE
)
_KNOWN_COMMANDS = (
    "pytest",
    "npm",
    "pnpm",
    "yarn",
    "bun",
    "uv",
    "pip",
    "python",
    "python3",
    "node",
    "npx",
    "ruff",
    "git",
    "make",
    "docker",
    "podman",
    "fly",
    "curl",
    "go",
    "cargo",
    "mix",
    "gradle",
    "mvn",
)


def _canonical_rule_body(body: str) -> str:
    # Exact duplicate cleanup must not rewrite whitespace inside commands or
    # quoted prose. Only the extraction boundary is removed.
    return body.strip()


def _extract_rule_body(line: str) -> str | None:
    raw = line.strip()
    if not raw or raw.startswith(">") or raw.startswith("<!--"):
        return None

    list_match = _LIST_RE.match(line)
    if list_match:
        return list_match.group(1).strip()
    if _DIRECTIVE_RE.match(raw):
        return raw
    return None


def _is_conditional(body: str) -> bool:
    return bool(_CONDITION_RE.search(body))


def _normalize_command(value: str) -> str:
    return _canonical_rule_body(value).strip("` ").lower()


def _extract_command(body: str) -> str | None:
    inline_commands = re.findall(r"`([^`\n]+)`", body)
    for candidate in inline_commands:
        normalized = _normalize_command(candidate)
        if normalized.startswith(_KNOWN_COMMANDS):
            return normalized

    command_match = _COMMAND_RE.search(body)
    return _normalize_command(command_match.group(0)) if command_match else None


def _safe_rule_cleanup_candidate(line: str, *, is_import: bool) -> bool:
    """Return whether an exact duplicate may remove this physical line.

    Indented lines may be nested lists or indented code, and numbered lists can
    carry meaningful sequence semantics. Keep both report-only even when their
    prose is identical. Imports are also retained because moving or repeating
    an include can affect the instruction graph.
    """
    if is_import or line != line.lstrip() or _CHECKBOX_RE.match(line):
        return False
    stripped = line.strip()
    if re.match(r"^\d+[.)]\s+", stripped):
        return False
    return True


def _has_indented_followup(lines: list[str], line_index: int) -> bool:
    """Detect a child or continuation belonging to a top-level rule line."""
    for following_index in range(line_index + 1, len(lines)):
        following = lines[following_index]
        stripped = following.strip()
        if not stripped:
            continue
        return following != following.lstrip()
    return False


def _mask_html_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """Remove HTML comments while retaining text outside them on each line."""
    pieces: list[str] = []
    cursor = 0
    while cursor < len(line):
        if in_comment:
            close = line.find("-->", cursor)
            if close < 0:
                return "".join(pieces), True
            cursor = close + 3
            in_comment = False
            continue

        opening = line.find("<!--", cursor)
        if opening < 0:
            pieces.append(line[cursor:])
            break
        pieces.append(line[cursor:opening])
        cursor = opening + 4
        in_comment = True
    return "".join(pieces), in_comment


def _is_relative_link_target(target: str) -> bool:
    """Classify a Markdown target without resolving or touching the filesystem."""
    cleaned = unquote(target.strip())
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0].strip().replace("\\", "/")
    if not cleaned:
        return False
    return not (
        cleaned.startswith("/")
        or cleaned.startswith("//")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", cleaned)
    )


def _section_key(
    headings: list[tuple[int, str, int]],
    details: list[int],
) -> tuple[tuple[int, str, int], ...]:
    # Details scopes are represented as synthetic heading entries so identical
    # rules in separate collapsible blocks never become one cleanup candidate.
    detail_entries = [(7, "<details>", serial) for serial in details]
    return tuple([*headings, *detail_entries])


def _extract_link_targets(line: str) -> list[str]:
    # Inline code is not Markdown link syntax. Mask it before scanning so an
    # example such as ``[text](missing.md)`` remains untouched and unreported.
    masked = re.sub(r"`[^`\n]*`", "", line)
    targets: list[str] = []
    for match in _INLINE_LINK_RE.finditer(masked):
        targets.append((match.group(1) or match.group(2) or "").strip())
    reference_match = _REFERENCE_LINK_RE.match(masked)
    if reference_match:
        targets.append((reference_match.group(1) or reference_match.group(2) or "").strip())
    return targets


def _canonical_rule_identity(line: str, body: str) -> str:
    checkbox = _CHECKBOX_RE.match(line)
    if checkbox:
        # Checked and unchecked tasks are different instructions. Keep their
        # state in the identity and never offer either line for cleanup.
        return f"[{checkbox.group(1).lower()}] {_canonical_rule_body(body)}"
    return _canonical_rule_body(body)


def _scan_file(
    file: InstructionFile,
) -> tuple[list[_RuleLine], list[_Link], list[_ImportReference], int]:
    rules: list[_RuleLine] = []
    links: list[_Link] = []
    imports: list[_ImportReference] = []
    protected_lines = 0
    headings: list[tuple[int, str, int]] = []
    details: list[int] = []
    heading_serial = 0
    detail_serial = 0
    in_fence = False
    fence_char: str | None = None
    fence_length = 0
    in_html_comment = False

    lines = file.content.splitlines(keepends=True)
    for line_index, line_with_newline in enumerate(lines):
        line = line_with_newline.rstrip("\r\n")
        line_number = line_index + 1
        fence_match = _FENCE_RE.match(line)
        if in_fence:
            closes_fence = (
                fence_match
                and fence_match.group(1)[0] == fence_char
                and len(fence_match.group(1)) >= fence_length
                and not line[fence_match.end() :].strip()
            )
            if closes_fence:
                in_fence = False
                fence_char = None
                fence_length = 0
            protected_lines += 1
            continue

        original_visible_line = line
        line, in_html_comment = _mask_html_comments(line, in_html_comment)
        if not line.strip():
            if in_html_comment:
                protected_lines += 1
            continue

        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            in_fence = True
            fence_char = marker[0]
            fence_length = len(marker)
            protected_lines += 1
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).rstrip("#").strip()
            heading_serial += 1
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title, heading_serial))
            protected_lines += 1
            continue

        lowered = line.strip().lower()
        if lowered.startswith("<details"):
            detail_serial += 1
            details.append(detail_serial)
            protected_lines += 1
        elif lowered.startswith("</details"):
            protected_lines += 1

        import_match = _IMPORT_RE.match(line)
        rule_body = _extract_rule_body(line)
        if rule_body:
            conditional = _is_conditional(rule_body)
            if conditional:
                protected_lines += 1
            rules.append(
                _RuleLine(
                    path=file.path,
                    line_index=line_index,
                    line_number=line_number,
                    section_key=_section_key(headings, details),
                    canonical=_canonical_rule_identity(line, rule_body),
                    body=rule_body,
                    conditional=conditional,
                    command=_extract_command(rule_body),
                    negative=bool(_NEGATIVE_RE.match(rule_body)),
                    positive=bool(_POSITIVE_RE.match(rule_body))
                    and not bool(_NEGATIVE_RE.match(rule_body)),
                    safe_to_remove=(
                        _safe_rule_cleanup_candidate(line, is_import=import_match is not None)
                        and original_visible_line == line
                        and not _has_indented_followup(lines, line_index)
                    ),
                )
            )

        for target in _extract_link_targets(line):
            if target:
                links.append(_Link(path=file.path, line_number=line_number, target=target))

        if import_match:
            target = import_match.group("at") or import_match.group("word") or ""
            imports.append(_ImportReference(path=file.path, line_number=line_number, target=target))
            protected_lines += 1

        if lowered.startswith("</details") and details:
            details.pop()

    return rules, links, imports, protected_lines


def _location(item: _RuleLine | _Link | _ImportReference) -> RelatedLocation:
    return RelatedLocation(path=item.path, line=item.line_number)


def _resolve_relative_link(source_path: str, target: str) -> str | None:
    cleaned = unquote(target.strip())
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0].strip().replace("\\", "/")
    if not cleaned:
        return None
    if (
        cleaned.startswith("/")
        or cleaned.startswith("//")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", cleaned)
    ):
        return None

    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), cleaned))
    if resolved in {"", ".", ".."} or resolved.startswith("../"):
        return None
    return resolved


def _unified_diff(path: str, original: str, suggested: str) -> str:
    if original == suggested:
        return ""
    old_lines = original.splitlines(keepends=True)
    new_lines = suggested.splitlines(keepends=True)
    raw_diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=path,
        tofile=f"{path} (suggested)",
        # Keep control headers on separate lines even when source lines
        # already carry their own newline terminators.
        lineterm="\n",
    )

    output: list[str] = []
    for item in raw_diff:
        if item.startswith(("--- ", "+++ ", "@@ ")):
            output.append(item)
            continue
        output.append(item if item.endswith(("\n", "\r")) else f"{item}\n")
        if not item.endswith(("\n", "\r")):
            output.append("\\ No newline at end of file\n")
    return "".join(output)


def _finding_sort_key(
    finding: InstructionReviewFinding, file_order: dict[str, int]
) -> tuple[int, int, str, str]:
    kind_order = {
        "duplicate_rule": 0,
        "potential_conflict": 1,
        "stale_link": 2,
        "context_split": 3,
    }
    return (
        file_order.get(finding.path, len(file_order)),
        finding.line,
        str(kind_order.get(finding.kind, 99)),
        finding.message,
    )


def analyze_instruction_review(req: InstructionReviewRequest) -> InstructionReviewResponse:
    """Review submitted instruction text deterministically and return report-only edits."""
    file_order = {file.path: index for index, file in enumerate(req.files)}
    all_rules: list[_RuleLine] = []
    all_links: list[_Link] = []
    all_imports: list[_ImportReference] = []
    protected_lines = 0

    for file in req.files:
        result = _scan_file(file)
        rules, links, imports, protected = result
        all_rules.extend(rules)
        all_links.extend(links)
        all_imports.extend(imports)
        protected_lines += protected

    findings: list[InstructionReviewFinding] = []
    remove_lines: set[tuple[str, int]] = set()

    global_first: dict[str, _RuleLine] = {}
    scope_first: dict[tuple[str, tuple[tuple[int, str, int], ...], str], _RuleLine] = {}
    for rule in all_rules:
        first_global = global_first.get(rule.canonical)
        if first_global is None:
            global_first[rule.canonical] = rule
            scope_first[(rule.path, rule.section_key, rule.canonical)] = rule
            continue

        scope_id = (rule.path, rule.section_key, rule.canonical)
        first_same_scope = scope_first.get(scope_id)
        related = first_same_scope or first_global
        same_scope = first_same_scope is not None
        removable = (
            same_scope
            and rule.line_index == related.line_index + 1
            and rule.safe_to_remove
            and related.safe_to_remove
            and not rule.conditional
            and not related.conditional
        )
        if removable:
            remove_lines.add((rule.path, rule.line_index))

        if removable:
            message = "Exact duplicate rule in the same heading section; the later plain line is suggested for removal."
            severity: FindingSeverity = "info"
        elif rule.conditional or related.conditional:
            message = (
                "Exact duplicate rule detected, but its condition is preserved in the suggestion."
            )
            severity = "warning"
        elif same_scope:
            message = (
                "Exact duplicate rule detected in the same heading section; it was kept for review."
            )
            severity = "warning"
        else:
            message = "Exact rule text appears in another file or heading section; scope may differ, so it was kept."
            severity = "warning"

        findings.append(
            InstructionReviewFinding(
                kind="duplicate_rule",
                severity=severity,
                message=message,
                path=rule.path,
                line=rule.line_number,
                related=[_location(related)],
            )
        )
        scope_first.setdefault(scope_id, rule)

    positives: dict[str, list[_RuleLine]] = {}
    positive_counts: dict[str, int] = {}
    negatives: dict[str, list[_RuleLine]] = {}
    for rule in all_rules:
        if not rule.command:
            continue
        if rule.positive:
            positive_counts[rule.command] = positive_counts.get(rule.command, 0) + 1
            locations = positives.setdefault(rule.command, [])
            if len(locations) < MAX_CONFLICT_RELATED:
                locations.append(rule)
        if rule.negative:
            negative_locations = negatives.setdefault(rule.command, [])
            if len(negative_locations) < MAX_CONFLICT_FINDINGS:
                negative_locations.append(rule)

    conflict_findings = 0
    for command, negative_rules in negatives.items():
        positive_rules = positives.get(command, [])
        if not positive_rules:
            continue
        for negative in negative_rules:
            if conflict_findings >= MAX_CONFLICT_FINDINGS:
                break
            related = [_location(positive) for positive in positive_rules]
            total_positive = positive_counts[command]
            suffix = (
                f" (showing {len(related)} of {total_positive} matching positive locations)"
                if total_positive > len(related)
                else ""
            )
            findings.append(
                InstructionReviewFinding(
                    kind="potential_conflict",
                    severity="warning",
                    message=(
                        f"Potential conflict for the literal command `{command}`: another rule permits or asks for it, "
                        "while this rule prohibits it. This is a literal match, not a full semantic analysis; review manually."
                        f"{suffix}"
                    ),
                    path=negative.path,
                    line=negative.line_number,
                    related=related,
                )
            )
            conflict_findings += 1

    known_repo_files = set(req.known_repo_files) if req.known_repo_files is not None else None
    for link in all_links:
        if known_repo_files is None:
            if _is_relative_link_target(link.target):
                findings.append(
                    InstructionReviewFinding(
                        kind="stale_link",
                        severity="info",
                        message=f"Relative Markdown link `{link.target}` was not verified because known_repo_files was not provided.",
                        path=link.path,
                        line=link.line_number,
                    )
                )
            continue

        resolved = _resolve_relative_link(link.path, link.target)
        if resolved is None:
            # URLs, anchors, and links that leave the supplied relative root are
            # outside this report's stale-link check.
            if _is_relative_link_target(link.target):
                findings.append(
                    InstructionReviewFinding(
                        kind="stale_link",
                        severity="warning",
                        message=f"Relative Markdown link `{link.target}` cannot be matched safely to known_repo_files; review it manually.",
                        path=link.path,
                        line=link.line_number,
                    )
                )
            continue

        if resolved not in known_repo_files:
            findings.append(
                InstructionReviewFinding(
                    kind="stale_link",
                    severity="warning",
                    message=f"Relative Markdown link target `{resolved}` is not present in known_repo_files; review whether it is stale.",
                    path=link.path,
                    line=link.line_number,
                )
            )

    for reference in all_imports:
        findings.append(
            InstructionReviewFinding(
                kind="context_split",
                severity="info",
                message=(
                    f"This file references `{reference.target}`. Splitting instructions into files does not automatically cut context; "
                    "the analyzer reports each submitted file separately."
                ),
                path=reference.path,
                line=reference.line_number,
            )
        )

    reviewed_files: list[ReviewedInstructionFile] = []
    for file in req.files:
        original_lines = file.content.splitlines(keepends=True)
        suggested = "".join(
            line
            for line_index, line in enumerate(original_lines)
            if (file.path, line_index) not in remove_lines
        )
        reviewed_files.append(
            ReviewedInstructionFile(
                path=file.path,
                original=file.content,
                suggested=suggested,
                diff=_unified_diff(file.path, file.content, suggested),
            )
        )

    findings.sort(key=lambda item: _finding_sort_key(item, file_order))
    conflict_count = sum(finding.kind == "potential_conflict" for finding in findings)
    stale_count = sum(finding.kind == "stale_link" for finding in findings)
    context_count = sum(finding.kind == "context_split" for finding in findings)
    line_count = sum(len(file.content.splitlines()) for file in req.files)

    summary = InstructionReviewSummary(
        files_reviewed=len(req.files),
        lines_reviewed=line_count,
        findings_count=len(findings),
        duplicate_lines_removed=len(remove_lines),
        potential_conflicts=conflict_count,
        stale_links=stale_count,
        context_notes=context_count,
        changed_files=sum(file.original != file.suggested for file in reviewed_files),
        preserved_lines=protected_lines,
    )
    return InstructionReviewResponse(findings=findings, files=reviewed_files, summary=summary)


def review_instruction_files(
    files: list[InstructionFile],
    *,
    known_repo_files: list[str] | None = None,
) -> InstructionReviewResponse:
    """Convenience wrapper for callers that already have validated file models."""
    return analyze_instruction_review(
        InstructionReviewRequest(files=files, known_repo_files=known_repo_files)
    )
