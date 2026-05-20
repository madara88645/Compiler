# Jules — Prompt Compiler (myCompiler)

**Read before any task:** [CLAUDE.md](../CLAUDE.md) at the repo root.

## What `.jules/` is

| File | Role |
|------|------|
| `instructions.md` | **Authoritative** rules for Jules |
| `bolt.md` | Performance learnings (compiler, RAG index, caching) |
| `palette.md` | UI / UX learnings (`web/`) |
| `sentinel.md` | Security learnings |

Treat journal entries as **context**, not tasks. Do not refactor unrelated modules because an old optimization note exists.

## Hard rules

1. **Provider-agnostic core:** Keep compiler/heuristics provider-neutral; adapter-specific behavior stays under `app/adapters/` and integrations.
2. **Secrets:** Never expose `.env`, credentials, or database URLs in code, logs, or PR text.
3. **Generated artifacts:** Treat emitted agent packs, skills, and MCP stubs as **untrusted until reviewed** (see CLAUDE.md Security).
4. **Conservative mode:** Do not invent APIs or requirements when conservative / policy-aware paths apply.
5. **Public product auth:** Do not introduce end-user Prompt Compiler API key requirements, browser API-key inputs, or hidden proxy-secret assumptions for public web/app routes. Open-source users should be able to use the product without learning `x-api-key`, `PROMPTC_SERVER_API_KEY`, or similar internal knobs.
6. **Scope:** Focused tests before full suites (`python -m pytest tests/ -q` or targeted files per CLAUDE.md).

## Performance (Bolt)

- RAG/SQLite caching notes in `bolt.md` apply to **hot paths you are already changing** — verify with profiling; avoid cache layers that thrash (e.g. `lru_cache` smaller than working set during full scans).
- Hoist repeated `getattr`/constraint checks only when the loop is proven hot.

## Verification (from CLAUDE.md)

- Backend: `python -m pytest tests/ -q`
- Focused: `python -m pytest tests/test_export_adapters.py tests/test_llm_providers.py -q`
- MCP: `python -m pytest integrations/mcp-server/test_server.py -q`
- Frontend: `cd web && npm run test` · `cd web && npm run build`
- Dev: `python -m uvicorn api.main:app --reload --port 8080` · `cd web && npm run dev`

## Appending learnings

Use `## YYYY-MM-DD - Title` with **Learning** and **Action** sections. No merge conflict markers.
