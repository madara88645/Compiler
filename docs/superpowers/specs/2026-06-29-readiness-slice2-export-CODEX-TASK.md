# Codex Task — Readiness Slice 2: executable .md/.json export

**Mode:** autonomous loop. Keep editing until the threshold below is green, then stop.

## Goal
Make the compile output **exportable as an executable-feeling `.md` document and a
machine-readable `.json` object**, and wire the already-built readiness markdown
into the product surfaces.

## Background (already shipped)
- Slice 1 (#879) computes a `ReadinessReport{verdict, signals, questions}` via
  `app/readiness/analyzer.py::analyze_readiness` and surfaces it on the `/compile`
  response as `readiness` (a dict).
- `app/readiness/markdown.py::report_to_markdown(report)` already renders a report
  as markdown (`## Readiness: <verdict> — <title>` + `### Signals` / `### Clarify first`)
  but is **not wired into any API/output** yet. Reuse it — do not reimplement it.

## Contract to implement
1. **`POST /compile`** response gains a `readiness_markdown: str` field, built by
   passing the same `ReadinessReport` through `report_to_markdown`.
2. **`POST /compile/export`** (new endpoint; same request body as `/compile`) returns:
   ```json
   { "markdown": "<self-contained document>", "json": { ... }, "filename": "<name>.md" }
   ```
   - `markdown` is one self-contained document containing, as `##` sections:
     **System Prompt**, **User Prompt**, **Plan**, and the **Readiness** section
     (the latter from `report_to_markdown`, i.e. the literal `## Readiness:` header).
     It must embed the real compiled prompt text, not empty placeholders.
   - `json` is the structured result and must include at least the keys
     `readiness` (dict with `verdict`), `system_prompt`, `user_prompt`, `plan`.
   - `filename` ends with `.md`.
3. **Agent pack manifests** (`POST /agent-packs/claude`, see `app/adapters/agent_packs.py`)
   include the readiness markdown section, so at least one manifest file's `content`
   contains the `## Readiness:` header. Analyze readiness from the request `goal`.

## Threshold = definition of done
- `python -m pytest tests/test_readiness_export.py -q` — **all pass**.
- `python -m pytest tests/ -q` — **full suite stays green** (no regressions).
- `tests/test_readiness_export.py` is the locked threshold: **do not modify, weaken,
  or delete any assertion in it.** If a test seems wrong, stop and flag it rather than
  editing it.

## Likely files to touch
- `api/routes/compile.py` — add `readiness_markdown` to `CompileResponse`; add the
  `/compile/export` endpoint (reuse the existing compile path, don't fork the logic).
- `app/readiness/` — if you add a JSON helper, keep it symmetric with `report_to_markdown`.
- `app/adapters/agent_packs.py` — inject the readiness section into the built files.
- `web/lib/api/types.ts` — keep the TS types in sync if you change response shapes.

## Hard rules (from repo CLAUDE.md)
- Do NOT touch `.env`/secrets, auth provider settings, or LLM prompt text /
  response-format / temperature / max_tokens.
- OpenRouter is the only cloud provider — do not add Groq/OpenAI fallbacks.
- No end-user API-key requirements for public web flows.
- Keep changes small and scoped to this task. No unrelated refactors.
- Before finishing, lint changed files the way CI does (Smoke pins ruff 0.1.14):
  `uvx ruff@0.1.14 check --fix` and `uvx ruff@0.1.14 format` on changed files.

## Run commands
```bash
python -m pytest tests/test_readiness_export.py -q      # the threshold
python -m pytest tests/ -q                              # full suite (no regressions)
```
