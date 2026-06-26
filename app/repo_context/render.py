from __future__ import annotations

from typing import Any

from .adapters import coerce_repo_context_envelope, redact_absolute_paths, sanitize_display_path
from .models import RepoContextEnvelope, RepoContextMode


def _append_with_budget(lines: list[str], line: str, *, max_chars: int) -> bool:
    candidate_len = sum(len(existing) + 1 for existing in lines) + len(line) + 1
    if candidate_len > max_chars:
        return False
    lines.append(line)
    return True


def render_repo_context_for_llm(
    repo_context: RepoContextEnvelope | dict[str, Any],
    *,
    mode: RepoContextMode | str = "compact",
    max_chars: int | None = None,
) -> str:
    envelope = coerce_repo_context_envelope(repo_context)
    if envelope is None:
        return ""

    resolved_mode = "compact" if str(mode or "compact").strip().lower() == "compact" else "full"
    default_budget = 1_400 if resolved_mode == "compact" else 4_000
    budget = max_chars or min(envelope.budget.max_chars or default_budget, default_budget)
    active_summary = (
        envelope.summary.compact
        if resolved_mode == "compact" and envelope.summary.compact
        else envelope.summary.full
    )

    lines = [
        "## Repo Context (ground truth)",
        "Treat this as verified repository context. Only reference tools, APIs, file paths, manifests, or conventions visible here. If something is missing, mark it as a TODO or open question instead of guessing.",
        "",
    ]

    identity = envelope.repo_identity
    if identity.name:
        _append_with_budget(
            lines, f"- Repo: {redact_absolute_paths(identity.name)}", max_chars=budget
        )
    if identity.url:
        _append_with_budget(
            lines, f"- URL: {redact_absolute_paths(identity.url)}", max_chars=budget
        )
    if identity.default_branch:
        _append_with_budget(
            lines,
            f"- Default branch: {redact_absolute_paths(identity.default_branch)}",
            max_chars=budget,
        )
    if identity.ref:
        _append_with_budget(
            lines, f"- Ref: {redact_absolute_paths(identity.ref)}", max_chars=budget
        )
    if envelope.detected_stack:
        stack = ", ".join(redact_absolute_paths(str(item)) for item in envelope.detected_stack)
        _append_with_budget(lines, f"- Detected stack: {stack}", max_chars=budget)
    if envelope.files_used:
        files = ", ".join(sanitize_display_path(path) for path in envelope.files_used)
        _append_with_budget(lines, f"- Brief built from: {files}", max_chars=budget)

    if active_summary:
        _append_with_budget(lines, "", max_chars=budget)
        _append_with_budget(lines, f"### Repo brief ({resolved_mode})", max_chars=budget)
        _append_with_budget(lines, redact_absolute_paths(active_summary), max_chars=budget)

    if envelope.snippets:
        _append_with_budget(lines, "", max_chars=budget)
        _append_with_budget(lines, "### Context snippets", max_chars=budget)
        for snippet in envelope.snippets:
            path = sanitize_display_path(snippet.display_path)
            content = redact_absolute_paths(snippet.content).strip()
            if not content:
                continue
            block = f"#### File: {path}\n```\n{content}\n```"
            if not _append_with_budget(lines, block, max_chars=budget):
                _append_with_budget(
                    lines, "- Additional snippets omitted due to context budget.", max_chars=budget
                )
                break

    _append_with_budget(lines, "", max_chars=budget)
    _append_with_budget(
        lines,
        "Reminder: this context is bounded and path-safe. Do not make file-level implementation claims unless the file is listed above.",
        max_chars=budget,
    )

    rendered = "\n".join(lines).rstrip()
    if len(rendered) > budget:
        rendered = rendered[: budget - 3].rstrip() + "..."
    return redact_absolute_paths(rendered)
