# Codex Task — CLI `compile-export` command

**Mode:** autonomous loop. Keep editing until the threshold below is green, then stop.

## Goal
Bring the executable export from #887 to the command line: a `compile-export`
command that writes the compile output as an executable-feeling `.md` document and
a structured `.json` file, mirroring the `POST /compile/export` endpoint.

## Background (already shipped, #887)
- `POST /compile/export` returns `{ markdown, json, filename }`.
- The markdown is a self-contained document with these `##` sections:
  **System Prompt**, **User Prompt**, **Plan**, and **Readiness** (the latter from
  `app/readiness/markdown.py::report_to_markdown`, i.e. the literal `## Readiness:`).
- The rendering helper is `api/routes/compile.py::_render_compile_export`.
- The CLI is **typer**-based (`cli/commands/_base.py::app`); `cli/commands/compile_cmd.py`
  already has `_run_compile` and uses `cli/commands/_helpers.py::_write_output`.

## Contract to implement
Add a typer command named **`compile-export`** (so `runner.invoke(app, ["compile-export", ...])`
works):
- Positional arg: `TEXT` — the request text.
- Option: `--out-dir PATH` — optional output directory.
- Behavior:
  - With `--out-dir DIR`: write `DIR/compile-export.md` (the self-contained export
    document) and `DIR/compile-export.json` (the structured result). Create the dir
    if needed.
  - Without `--out-dir`: print the export markdown to stdout.
- The markdown must contain `## System Prompt`, `## User Prompt`, `## Plan`, and the
  `## Readiness:` section, and embed the real compiled prompt text (no placeholders).
- The JSON must include at least `readiness` (dict with `verdict`), `system_prompt`,
  `user_prompt`, `plan`.
- Must run **fully offline / deterministically** (no LLM/network call) — mirror the
  existing CLI compile default. Tests run in CI without network.

## DRY note
Prefer extracting the export markdown rendering into a small shared helper under
`app/` (used by both the endpoint and the CLI) rather than importing the API layer
from the CLI or duplicating the renderer. The threshold pins behaviour, not
internals — pick the cleanest implementation.

## Threshold = definition of done
- `python -m pytest tests/test_cli_compile_export.py -q` — **all pass**.
- `python -m pytest tests/ -q` — **full suite stays green** (no regressions).
- `tests/test_cli_compile_export.py` is the locked threshold: **do not modify, weaken,
  or delete any assertion.** If a test seems wrong, stop and flag it.

## Hard rules (from repo CLAUDE.md)
- Do NOT touch `.env`/secrets, auth settings, or LLM prompt text / response-format /
  temperature / max_tokens.
- OpenRouter is the only cloud provider — no Groq/OpenAI fallbacks.
- Keep changes small and scoped. No unrelated refactors beyond the optional DRY extract.
- Lint changed files the way CI does (Smoke pins ruff 0.1.14):
  `uvx ruff@0.1.14 check --fix` and `uvx ruff@0.1.14 format`.

## Run commands
```bash
python -m pytest tests/test_cli_compile_export.py -q   # the threshold
python -m pytest tests/ -q                             # full suite (no regressions)
```
