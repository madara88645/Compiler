from __future__ import annotations

import re

# Wrapper labels models occasionally prepend even though optimizer.md tells them not to.
# Anchored to the first non-blank line so we never touch content that lives below or
# inside fenced code blocks.
_WRAPPER_LINE_RE = re.compile(
    r"""^\s*
        (?:[#>*\-\s]*)               # leading markdown decoration (#, >, *, -)
        (?:\*\*)?                    # optional bold opener
        (?:optimized\s+prompt|optimized|result|output|here\s+is\s+the\s+optimized\s+prompt)
        (?:\*\*)?                    # optional bold closer
        \s*[:\-]?\s*$                # optional trailing colon/dash
    """,
    re.IGNORECASE | re.VERBOSE,
)


def strip_wrapper_labels(text: str) -> str:
    """Strip a leading wrapper label (e.g. ``**Optimized Prompt**:``) from optimizer output.

    Only the first non-blank line is examined and only when it is *exclusively* a
    wrapper label. Code fences, placeholders like ``{{var}}``, file paths, and
    every other line are left untouched.
    """

    if not text:
        return text

    lines = text.splitlines()
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return text

    if not _WRAPPER_LINE_RE.match(lines[idx]):
        return text

    rest = lines[idx + 1 :]
    while rest and not rest[0].strip():
        rest.pop(0)

    trailing_newline = "\n" if text.endswith("\n") else ""
    return "\n".join(rest) + trailing_newline
