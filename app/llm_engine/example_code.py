from __future__ import annotations

from dataclasses import dataclass
import re

AGENT_EXAMPLE_CODE_WARNING = (
    "Example Code was requested, but the generator returned a text-only prompt. "
    "You can still use this result or try generating again."
)

SKILL_EXAMPLE_CODE_WARNING = (
    "Example Code was requested, but the generator returned a text-only skill definition. "
    "You can still use this result or try generating again."
)

_FENCED_CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_-]*\n[\s\S]*?\n```")
_NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)

_SINGLE_AGENT_SECTION_RE = re.compile(
    r"^## Example Code \(Pseudo-code Skeleton\)\s*$", re.MULTILINE
)
_MULTI_AGENT_SECTION_RE = re.compile(
    r"^## Swarm Example Code \(Pseudo-code Skeleton\)\s*$", re.MULTILINE
)
_SKILL_SECTION_RE = re.compile(r"^## Implementation Example\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ExampleCodeInspection:
    example_code_requested: bool
    example_code_present: bool
    example_code_warning: str | None


def _section_contains_fenced_code(markdown: str, section_pattern: re.Pattern[str]) -> bool:
    match = section_pattern.search(markdown)
    if match is None:
        return False

    section_body = markdown[match.end() :]
    next_section = _NEXT_SECTION_RE.search(section_body)
    if next_section is not None:
        section_body = section_body[: next_section.start()]

    return _FENCED_CODE_BLOCK_RE.search(section_body) is not None


def inspect_agent_example_code(markdown: str, *, multi_agent: bool, requested: bool) -> ExampleCodeInspection:
    if not requested:
        return ExampleCodeInspection(
            example_code_requested=False,
            example_code_present=False,
            example_code_warning=None,
        )

    section_pattern = _MULTI_AGENT_SECTION_RE if multi_agent else _SINGLE_AGENT_SECTION_RE
    present = _section_contains_fenced_code(markdown, section_pattern)
    return ExampleCodeInspection(
        example_code_requested=True,
        example_code_present=present,
        example_code_warning=None if present else AGENT_EXAMPLE_CODE_WARNING,
    )


def inspect_skill_example_code(markdown: str, *, requested: bool) -> ExampleCodeInspection:
    if not requested:
        return ExampleCodeInspection(
            example_code_requested=False,
            example_code_present=False,
            example_code_warning=None,
        )

    present = _section_contains_fenced_code(markdown, _SKILL_SECTION_RE)
    return ExampleCodeInspection(
        example_code_requested=True,
        example_code_present=present,
        example_code_warning=None if present else SKILL_EXAMPLE_CODE_WARNING,
    )
