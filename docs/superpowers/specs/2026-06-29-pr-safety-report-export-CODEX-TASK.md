# Codex Task — `POST /pr-safety/report/export`

**Mode:** autonomous loop. Keep editing until the threshold below is green, then stop.

## Goal
Expose the existing GitHub-ready PR Safety markdown through the API, mirroring
`POST /compile/export` (#887). Today the markdown renderer is CLI-only; web, CI, and
the planned GitHub Action have no server-side way to fetch it.

## Background (already shipped)
- `POST /pr-safety/report` (`api/routes/pr_safety.py`) returns a structured
  `PrSafetyReport` (verdict, title, changed_files, risky_areas, test_coverage,
  branch_freshness, scope_match, recommendations).
- `app/pr_safety/markdown.py::report_to_markdown(report: PrSafetyReport) -> str`
  already renders that report as a GitHub-ready markdown document
  (`# PR Safety Report`, `**Verdict:**`, `## Changed files`, `## Risky areas`, …).
  It is offline/deterministic and currently used **only** by `cli/commands/pr_safety.py`.
- For reference, `POST /compile/export` returns `{ markdown, json, filename }`.

## Contract to implement
Add **`POST /pr-safety/report/export`** taking the same request body as
`/pr-safety/report` (`PrSafetyReportRequest`) and returning:
```json
{ "markdown": "<report_to_markdown output>", "json": { ...PrSafetyReport... }, "filename": "<name>.md" }
```
- Reuse the **existing** report-building path (do not fork the analyzer) and the
  **existing** `report_to_markdown` (do not write a second renderer).
- `json` must be the same structured `PrSafetyReport` as `/pr-safety/report`.
- `filename` ends with `.md`.
- Keep it rate-limited like the other pr-safety / compile routes.

## Threshold = definition of done
- `python -m pytest tests/test_pr_safety_export.py -q` — **all pass**.
- `python -m pytest tests/ -q` — **full suite stays green** (no regressions).
- `tests/test_pr_safety_export.py` is the locked threshold: **do not modify, weaken,
  or delete any assertion.** If a test seems wrong, stop and flag it.

## Likely files to touch
- `api/routes/pr_safety.py` — add the endpoint + a small response model
  (`{ markdown, json, filename }`); reuse the analyzer call already used by
  `/pr-safety/report` and `app/pr_safety/markdown.py::report_to_markdown`.
- `web/lib/api/*` — only if you change shared response shapes (keep TS types in sync).

## Hard rules (from repo CLAUDE.md)
- Do NOT touch `.env`/secrets, auth settings, or LLM prompt text / params.
- OpenRouter is the only cloud provider — no Groq/OpenAI fallbacks.
- No end-user API-key requirements for public web flows.
- Keep changes small and scoped. No unrelated refactors.
- Lint changed files the way CI does (Smoke pins ruff 0.1.14):
  `uvx ruff@0.1.14 check --fix` and `uvx ruff@0.1.14 format`.

## Run commands
```bash
python -m pytest tests/test_pr_safety_export.py -q   # the threshold
python -m pytest tests/ -q                           # full suite (no regressions)
```
