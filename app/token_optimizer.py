from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional, Tuple

from app.text_utils import estimate_tokens


_FENCE_OPEN_RE = re.compile(r"^\s*(```+|~~~+)")


@dataclass(frozen=True)
class OptimizeStats:
    before_chars: int
    after_chars: int
    before_tokens: int
    after_tokens: int
    passes: int
    met_max_chars: bool
    met_max_tokens: bool
    changed: bool


def optimize_text(
    text: str,
    *,
    max_chars: Optional[int] = None,
    max_tokens: Optional[int] = None,
    token_ratio: float = 4.0,
) -> Tuple[str, OptimizeStats]:
    """Deterministically shorten text without changing semantic content.

    This is a conservative optimizer intended to reduce LLM prompt cost by removing
    redundant whitespace and duplication while preserving Markdown structure.

    - Fenced code blocks (``` / ~~~) are preserved verbatim.
    - The optimizer is best-effort for budgets; it will not truncate content.
    """

    src = text or ""
    before_chars = len(src)
    before_tokens = estimate_tokens(src)

    # If a token budget is provided but no explicit char budget, derive a char budget
    # using the same convention as RAG: token_ratio ~= chars/token.
    derived_max_chars = max_chars
    if max_tokens is not None and derived_max_chars is None:
        try:
            derived_max_chars = max(0, int(max_tokens * float(token_ratio)))
        except Exception:
            derived_max_chars = None

    has_budget = derived_max_chars is not None or max_tokens is not None

    # Apply increasingly aggressive (but still safe) whitespace reductions until we meet budget.
    level = 1
    out = src
    passes = 0
    while True:
        passes += 1
        candidate = _optimize_once(out, level=level)
        if candidate == out:
            # No further progress possible at this level.
            # Only escalate if we have a budget and still haven't met it.
            if has_budget and not _meets_budget(
                out, max_chars=derived_max_chars, max_tokens=max_tokens
            ):
                if level >= 3:
                    break
                level += 1
                continue
            break

        out = candidate

        if _meets_budget(out, max_chars=derived_max_chars, max_tokens=max_tokens):
            break

        if level >= 3:
            break
        level += 1

        # Safety guard against unexpected looping.
        if passes >= 6:
            break

    out = out.strip() if out.strip() else out.strip("\n")

    after_chars = len(out)
    after_tokens = estimate_tokens(out)

    met_chars = derived_max_chars is None or after_chars <= derived_max_chars
    met_tokens = max_tokens is None or after_tokens <= max_tokens

    return (
        out,
        OptimizeStats(
            before_chars=before_chars,
            after_chars=after_chars,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            passes=passes,
            met_max_chars=met_chars,
            met_max_tokens=met_tokens,
            changed=(out != src),
        ),
    )


def _meets_budget(text: str, *, max_chars: Optional[int], max_tokens: Optional[int]) -> bool:
    if max_chars is not None and len(text) > max_chars:
        return False
    if max_tokens is not None and estimate_tokens(text) > max_tokens:
        return False
    return True


def _optimize_once(text: str, *, level: int) -> str:
    parts = _split_fenced_code(text)
    out_parts: List[str] = []
    for kind, chunk in parts:
        if kind == "code":
            out_parts.append(chunk)
        else:
            out_parts.append(_optimize_markdown_text(chunk, level=level))
    combined = "".join(out_parts)
    # Normalize stray whitespace around code fences.
    combined = combined.replace("\r\n", "\n")
    return combined


def _split_fenced_code(text: str) -> List[Tuple[str, str]]:
    """Split into [('text'|'code', chunk)] preserving fence blocks verbatim."""

    s = (text or "").replace("\r\n", "\n")
    lines = s.splitlines(keepends=True)

    parts: List[Tuple[str, str]] = []
    buf: List[str] = []

    in_fence = False
    fence_marker = ""

    def flush(kind: str):
        nonlocal buf
        if not buf:
            return
        parts.append((kind, "".join(buf)))
        buf = []

    for line in lines:
        if not in_fence:
            m = _FENCE_OPEN_RE.match(line)
            if m:
                flush("text")
                in_fence = True
                fence_marker = m.group(1)
                buf.append(line)
            else:
                buf.append(line)
            continue

        # in fence
        buf.append(line)
        if _is_fence_close(line, fence_marker):
            flush("code")
            in_fence = False
            fence_marker = ""

    flush("code" if in_fence else "text")
    return parts


def _is_fence_close(line: str, fence_marker: str) -> bool:
    if not fence_marker:
        return False
    stripped = line.strip()
    if not stripped:
        return False
    fence_char = fence_marker[0]
    if fence_char not in ("`", "~"):
        return False
    # Close when we see a fence of the same char and at least the same length,
    # and no other content on the line.
    run = re.match(rf"^{re.escape(fence_char)}+", stripped)
    if not run:
        return False
    return len(run.group(0)) >= len(fence_marker) and stripped == run.group(0)


def _optimize_markdown_text(text: str, *, level: int) -> str:
    s = (text or "").replace("\r\n", "\n")

    # Trim trailing whitespace on each line.
    lines = [ln.rstrip() for ln in s.split("\n")]

    # Remove exact duplicate consecutive lines (excluding blanks which are handled below).
    deduped: List[str] = []
    prev = None
    for ln in lines:
        if prev is not None and ln == prev and ln.strip():
            continue
        deduped.append(ln)
        prev = ln

    # Normalize spacing for non-code, non-table lines.
    normalized: List[str] = []
    for ln in deduped:
        normalized.append(_normalize_line(ln, level=level))

    # Blank line handling.
    compacted: List[str] = []
    prev_blank = False
    for ln in normalized:
        is_blank = not ln.strip()
        if is_blank:
            if level >= 2:
                continue
            if prev_blank:
                continue
            compacted.append("")
            prev_blank = True
            continue
        compacted.append(ln)
        prev_blank = False

    out = "\n".join(compacted)
    return out


_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")


def _normalize_line(line: str, *, level: int) -> str:
    ln = line

    # Keep indented code blocks and tables untouched.
    if ln.startswith("    ") or ln.startswith("\t"):
        return ln
    if "|" in ln and _looks_like_table_row(ln):
        return ln

    # Optionally remove indentation before list markers (safe: doesn't change content).
    if level >= 3:
        m = _LIST_RE.match(ln)
        if m:
            ln = ln[len(m.group(1)) :]

    # Normalize spaces after list markers.
    m = _LIST_RE.match(ln)
    if m:
        prefix = ln[: m.end()]
        rest = ln[m.end() :]
        rest = re.sub(r"[ \t]{2,}", " ", rest).strip()
        return prefix + rest

    # Collapse internal runs of spaces/tabs.
    ln = re.sub(r"[ \t]{2,}", " ", ln).strip() if level >= 1 else ln
    return ln


def _looks_like_table_row(line: str) -> bool:
    # Conservative: if there are 2+ pipes, treat as table-ish.
    return line.count("|") >= 2
