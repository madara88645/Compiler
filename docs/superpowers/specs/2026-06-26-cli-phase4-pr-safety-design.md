# CLI Phase 4 — PR Safety command (design)

Date: 2026-06-26
Status: Implemented

## Goal

Expose the existing offline PR Safety analyzer (`app/pr_safety/`) on the CLI as
`prcompiler pr-safety`. No new product behavior — this is a thin, deterministic,
offline adapter over `analyze_pr_safety(...)`. The browser surface
(`web/app/pr-safety/`) remains the visual reference; the CLI mirrors its
Markdown output exactly.

## Constraints

- No network / GitHub / AI calls. `--from-git` only reads the local repo via
  stdlib `subprocess` (never `shell=True`).
- No changes to `app/pr_safety/analyzer.py`, `app/pr_safety/models.py`, or the
  web frontend. Core analysis stays provider-agnostic.
- No new dependencies.
- Preserve the existing 9 top-level commands; add a 10th (`pr-safety`).
- Phase 2 rule: machine formats (`json`, `md`) emit plain, unstyled text; only
  the `human` tier uses Rich.

## Contracts

`analyze_pr_safety(title, description, changed_files, *, commits_behind=None)`
returns a `PrSafetyReport` whose verdict is one of `merge | hold | split |
rebase`. Verdict precedence (from the analyzer): stale branch (>= 10 commits
behind) -> rebase; large changeset (>= 15 files, or >= 4 top-level dirs with
>= 8 files) -> split; risky/test-gap/scope-mismatch -> hold; otherwise merge.

## Components

- `app/pr_safety/markdown.py:report_to_markdown` — Python port of
  `web/app/pr-safety/markdown.ts:reportToMarkdown`, section-for-section.
- `app/pr_safety/git_context.py` — `resolve_base_ref`, `changed_files`,
  `commits_behind`, `head_commit_message`, plus `GitContextError`. Pure
  subprocess helpers, independently testable / monkeypatchable.
- `cli/render.py:render_pr_safety_report` — human-tier verdict panel + ruled
  sections, markup-safe via `rich.markup.escape`.
- `cli/commands/pr_safety.py` — the `pr-safety` Typer command.

## Output formats

- `human` (default): Rich verdict panel (verdict + title + per-signal status)
  then ruled sections (changed files, risky areas, test coverage, branch
  freshness, scope match, recommendations).
- `json`: `json.dumps(report.model_dump(), indent=2)`.
- `md`: GitHub-ready Markdown identical to the web port.

`--exit-code` makes the command exit 1 when the verdict is not `merge` (for CI
gating), while the default exit code stays 0 so the advisory never blocks.
