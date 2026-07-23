"""Section-aware, append-new-only merge of a generated CLAUDE.md into an existing one.

The user's existing content is preserved verbatim; only generated level-2 (``## ``)
sections whose heading the user lacks are appended, under a marker comment. Idempotent for
a fixed ``generated`` input. See the design spec for the full contract.
"""

from __future__ import annotations

import re

MARKER = "<!-- Added by Prompt Compiler: sections not already in your CLAUDE.md -->"

_HEADING_RE = re.compile(r"^##[ \t]+(.+?)\s*$")  # level-2 only; "##Foo" (no space) is not a heading
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")  # >=3 backticks or tildes after leading whitespace


def _heading_key(text: str) -> str:
    # Bolt Optimization: join(split()) is ~3x faster than re.sub for collapsing whitespace
    return " ".join(text.split()).casefold()


def _iter_sections(md: str) -> list[tuple[str, str]]:
    """(heading_key, section_text) for each level-2 section, fence-aware."""
    fence: tuple[str, int] | None = None
    out: list[tuple[str, str]] = []
    key: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        fence_m = _FENCE_RE.match(line.lstrip())
        if fence_m:
            run = fence_m.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif fence[0] == run[0] and len(run) >= fence[1]:
                fence = None
            if key is not None:
                buf.append(line)
            continue
        heading = None if fence is not None else _HEADING_RE.match(line)
        if heading:
            if key is not None:
                out.append((key, "\n".join(buf)))
            key = _heading_key(heading.group(1))
            buf = [line]
        elif key is not None:
            buf.append(line)
    if key is not None:
        out.append((key, "\n".join(buf)))
    return out


def merge_claude_md(existing: str, generated: str) -> str:
    """Append generated ``##`` sections the user lacks; preserve existing verbatim."""
    seen = {k for k, _ in _iter_sections(existing)}
    new_sections: list[str] = []
    for key, text in _iter_sections(generated):
        if key in seen:
            continue
        seen.add(key)
        new_sections.append(text.rstrip())
    if not new_sections:
        return existing
    return existing.rstrip() + "\n\n" + MARKER + "\n\n" + "\n\n".join(new_sections) + "\n"
