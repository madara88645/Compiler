# CLI Phase 4 — PR Safety command (plan)

Date: 2026-06-26
Status: Done

## Scope

Add a `pr-safety` CLI command over the existing offline analyzer. Additive only:
the 9 existing top-level commands are preserved; this is the 10th.

## Steps

1. `app/pr_safety/markdown.py` — `report_to_markdown(report)`, a section-for-section
   port of `web/app/pr-safety/markdown.ts`.
2. `app/pr_safety/git_context.py` — stdlib `subprocess` helpers
   (`resolve_base_ref`, `changed_files`, `commits_behind`, `head_commit_message`)
   plus `GitContextError`. No `shell=True`.
3. `cli/render.py` — `render_pr_safety_report(console, report)`, human-tier only,
   markup-safe.
4. `cli/commands/pr_safety.py` — `@app.command("pr-safety")`:
   - Inputs: `[FILES...]`, `-t/--title`, `--description`, `--files-from`,
     `--from-git`, `--base`, `--commits-behind`, `--format human|json|md`,
     `--out`, `--exit-code`.
   - Manual mode requires `--title` + `--description`; `--from-git` derives files
     + freshness and defaults title/description from the HEAD commit.
   - `human` -> Rich render; `json`/`md` -> plain text via `_write_output`.
   - `--exit-code` + verdict != merge -> exit 1.
5. `cli/commands/core.py` — side-effect import to register the command.
6. `tests/test_cli_phase3.py` — add `pr-safety` to the command-surface invariant.

## Tests (TDD)

- `tests/test_cli_phase4.py` — formats, verdict-driving inputs (split / rebase /
  merge), `--exit-code`, error paths, `--from-git` via monkeypatched helpers.
- `tests/test_pr_safety_markdown.py` — Markdown parity with the web TS renderer.

## Verdict-driving inputs (verified against the real analyzer)

- split: 20 changed `.py` files (>= 15 threshold).
- rebase: `--commits-behind 12` (>= 10 threshold) with a small clean changeset.
- merge: `app/foo.py` + `tests/test_foo.py`, `--commits-behind 0` (no risky /
  gap / mismatch / stale signals).

## Gates

- `pytest tests/test_cli_phase4.py tests/test_pr_safety_markdown.py tests/test_cli_phase3.py`
- `pytest tests/test_cli_phase1.py tests/test_cli_phase2.py tests/test_cli_console_refactor.py`
- Smoke: human / md / json / `--help`.
- ruff@0.1.14 check --fix + format on all changed files, then re-run gates.
