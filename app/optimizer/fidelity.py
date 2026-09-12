"""Small, deterministic guards for optimizer output fidelity.

The optimizer is allowed to rewrite prose, but it must not silently discard
machine-readable prompt material.  These checks are intentionally conservative
and return the source text when a required marker disappears.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]{1,200}\}\}|\$\{[^{}\n]{1,200}\}")
_URL_RE = re.compile(r"https?://[^\s<>'\"]+")
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})([^\n]*)$")
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
# Match complete runs first, then check for a path separator in Python.
# Requiring a slash after a greedy first segment can force regex backtracking.
_FILE_RE = re.compile(r"[\w.-]+(?:/[\w.-]+)*")


@dataclass(frozen=True)
class FidelityCheck:
    text: str
    preserved: bool
    missing: tuple[str, ...] = ()


def _fence_blocks(text: str) -> list[tuple[str, str]]:
    """Return (language, literal block) pairs, including closing fences."""

    blocks: list[tuple[str, str]] = []
    lines = (text or "").replace("\r\n", "\n").splitlines(keepends=True)
    current: list[str] = []
    marker = ""
    language = ""
    for line in lines:
        match = _FENCE_LINE_RE.match(line.rstrip("\n"))
        if not marker:
            if not match:
                continue
            marker, info = match.groups()
            language = info.strip().split()[0].lower() if info.strip() else ""
            current = [line]
            continue

        current.append(line)
        stripped = line.strip()
        if stripped.startswith(marker) and not stripped.strip(marker[0]):
            blocks.append((language, "".join(current)))
            current = []
            marker = ""
            language = ""

    if marker and current:
        # Preserve an unterminated fence as a protected literal block too.
        blocks.append((language, "".join(current)))
    return blocks


def _protected_values(source: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    values.extend(("placeholder", value) for value in _PLACEHOLDER_RE.findall(source or ""))
    values.extend(("URL", value.rstrip(".,;:!?)]}")) for value in _URL_RE.findall(source or ""))
    values.extend(("inline code", value) for value in _INLINE_CODE_RE.findall(source or ""))
    for match in _FILE_RE.finditer(source or ""):
        value = match.group()
        if "/" not in value:
            continue
        start = match.start()
        if start and source[start - 1] == "/":
            prefix = "~/" if start >= 2 and source[start - 2] == "~" else "/"
            value = prefix + value
        values.append(("file path", value))
    return values


def check_fidelity(source: str, candidate: str) -> FidelityCheck:
    """Check protected prompt markers without judging ordinary prose changes."""

    original = source or ""
    result = candidate or ""
    candidate_for_checks = result.replace("\r\n", "\n")
    missing: list[str] = []

    if original.strip() and not result.strip():
        missing.append("non-empty prompt")

    source_blocks = _fence_blocks(original)
    if source_blocks:
        # Preserve the complete literal block.  Rewriting code inside a prompt
        # can change executable behavior even when its language label survives.
        for _language, block in source_blocks:
            if block not in candidate_for_checks:
                missing.append("fenced code block")
                break

    for kind, value in _protected_values(original):
        if value and value not in candidate_for_checks:
            missing.append(kind)

    unique_missing = tuple(dict.fromkeys(missing))
    return FidelityCheck(
        text=original if unique_missing else result,
        preserved=not unique_missing,
        missing=unique_missing,
    )


def apply_fidelity_guard(
    source: str,
    candidate: str,
    *,
    empty_on_failure: bool = False,
) -> tuple[str, list[str]]:
    """Return guarded text and user-facing warnings.

    Main optimization output falls back to the source so a valid prompt is
    always available.  Optional translated variants are hidden when invalid,
    because showing the original language as an English suggestion is confusing.
    """

    check = check_fidelity(source, candidate)
    if check.preserved:
        return check.text, []

    details = ", ".join(check.missing)
    if empty_on_failure:
        return "", [
            f"English compact suggestion was hidden because it dropped protected content ({details})."
        ]
    return check.text, [
        f"Optimizer output dropped protected content ({details}); the original prompt was kept."
    ]
