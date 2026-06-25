from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import (
    GitHubRepoContextPayload,
    RepoContextBudget,
    RepoContextEnvelope,
    RepoContextIdentity,
    RepoContextSafety,
    RepoContextSnippet,
    RepoContextSummary,
)

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<!https:)(?<!http:)(?:~[/\\]|[A-Za-z]:[\\/]|/(?:Users|home|var|tmp|private|opt|Volumes)/)[^\s`'\"\)]*"
)
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def redact_absolute_paths(text: str) -> str:
    return _ABSOLUTE_PATH_RE.sub("[path-redacted]", str(text or ""))


def contains_absolute_path(text: str) -> bool:
    return bool(_ABSOLUTE_PATH_RE.search(str(text or "")))


def sanitize_display_path(raw_path: Any, *, cwd: Path | None = None) -> str:
    text = str(raw_path or "").strip().replace("\x00", "")
    if not text or text in {".", ".."}:
        return "unknown"

    normalized = text.replace("\\", "/")
    is_absolute = (
        normalized.startswith("/")
        or normalized.startswith("~/")
        or bool(_WINDOWS_DRIVE_RE.match(text))
    )

    if is_absolute:
        try:
            base = (cwd or Path.cwd()).resolve()
            relative = Path(text).expanduser().resolve(strict=False).relative_to(base)
            return sanitize_display_path(str(relative), cwd=cwd)
        except Exception:
            normalized = Path(normalized).name or "unknown"

    parts = []
    for part in normalized.split("/"):
        part = part.strip()
        if not part or part in {".", ".."}:
            continue
        safe = _SAFE_SEGMENT_RE.sub("_", part).strip(" .")
        if safe:
            parts.append(safe[:80])

    if not parts:
        return "unknown"
    return "/".join(parts[-8:])[:240]


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _clean_text(value: Any, *, max_chars: int) -> str:
    text = redact_absolute_paths(str(value or "")).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def github_payload_to_envelope(
    payload: dict[str, Any] | GitHubRepoContextPayload,
) -> RepoContextEnvelope:
    github_payload = (
        payload
        if isinstance(payload, GitHubRepoContextPayload)
        else GitHubRepoContextPayload.model_validate(payload)
    )
    requested_ref = github_payload.requested_ref or None
    files_used = _dedupe([sanitize_display_path(path) for path in github_payload.files_used])
    highlights = [_clean_text(item, max_chars=500) for item in github_payload.highlights]
    summary_full = _clean_text(github_payload.summary, max_chars=1_500)
    summary_compact = _clean_text(github_payload.summary_compact or "", max_chars=400) or None
    snippets = [
        RepoContextSnippet(
            display_path="repo highlights", content=item, source_label="GitHub brief"
        )
        for item in highlights[:6]
        if item
    ]

    return RepoContextEnvelope(
        source_type="github_public",
        repo_identity=RepoContextIdentity(
            name=github_payload.repo_full_name,
            url=github_payload.normalized_repo_url,
            default_branch=github_payload.default_branch,
            ref=requested_ref,
        ),
        summary=RepoContextSummary(full=summary_full, compact=summary_compact),
        detected_stack=[_clean_text(item, max_chars=120) for item in github_payload.detected_stack],
        files_used=files_used,
        snippets=snippets,
        budget=RepoContextBudget(max_chars=4_000),
        safety=RepoContextSafety(path_safe=True, contains_absolute_paths=False),
    )


def rag_results_to_envelope(
    results: list[dict[str, Any]], *, max_chars: int = 4_000
) -> RepoContextEnvelope:
    snippets: list[RepoContextSnippet] = []
    files_used: list[str] = []
    used_chars = 0
    truncated = False

    for item in results:
        display_path = sanitize_display_path(
            item.get("display_path") or item.get("path") or item.get("file") or "unknown"
        )
        content = _clean_text(item.get("content") or item.get("snippet") or "", max_chars=700)
        if not content:
            continue
        block_size = len(display_path) + len(content) + 32
        if used_chars + block_size > max_chars:
            truncated = True
            break
        snippets.append(
            RepoContextSnippet(
                display_path=display_path,
                content=content,
                score=item.get("hybrid_score") or item.get("similarity") or item.get("score"),
                source_label=str(item.get("source_label") or "RAG index"),
            )
        )
        files_used.append(display_path)
        used_chars += block_size

    return RepoContextEnvelope(
        source_type="rag_index",
        summary=RepoContextSummary(
            full="Opt-in local indexed context retrieved from the RAG index.",
            compact="Opt-in RAG context.",
        ),
        files_used=_dedupe(files_used),
        snippets=snippets,
        budget=RepoContextBudget(max_chars=max_chars, used_chars=used_chars, truncated=truncated),
        safety=RepoContextSafety(path_safe=True, contains_absolute_paths=False),
    )


def coerce_repo_context_envelope(value: Any) -> RepoContextEnvelope | None:
    if value is None:
        return None
    if isinstance(value, RepoContextEnvelope):
        return value
    if isinstance(value, GitHubRepoContextPayload):
        return github_payload_to_envelope(value)
    if not isinstance(value, dict):
        return None
    if value.get("source_type"):
        envelope = RepoContextEnvelope.model_validate(value)
        return RepoContextEnvelope(
            **{
                **envelope.model_dump(),
                "files_used": [sanitize_display_path(path) for path in envelope.files_used],
                "snippets": [
                    {
                        **snippet.model_dump(),
                        "display_path": sanitize_display_path(snippet.display_path),
                        "content": _clean_text(snippet.content, max_chars=2_000),
                    }
                    for snippet in envelope.snippets
                ],
                "safety": RepoContextSafety(
                    path_safe=True, contains_absolute_paths=False
                ).model_dump(),
            }
        )
    if value.get("normalized_repo_url") or value.get("repo_full_name"):
        return github_payload_to_envelope(value)
    if value.get("context_snippets"):
        snippets = value.get("context_snippets")
        if isinstance(snippets, list):
            return rag_results_to_envelope(snippets)
    return None


def repo_context_cache_fingerprint(value: Any) -> str:
    envelope = coerce_repo_context_envelope(value)
    if envelope is None:
        return ""
    payload = envelope.model_dump(mode="json")
    compact = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()[:16]
