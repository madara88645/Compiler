# RAG Context Injection → Opt-In (Default Off)

**Date:** 2026-06-27
**Status:** Approved (design) — pending implementation
**Branch:** `fix/rag-context-opt-in` (off `origin/main`)
**Type:** Behavior change + bug fix (path/context leak). Ship as **Draft PR** (prompt-output change → manual review).

## Problem

`compile_text_v2(text, offline_only=False)` defaults `offline_only=False`. In that mode the **Context Strategist** (`app/compiler.py:323`) runs automatically: it queries the machine-local SQLite FTS5 RAG index (`app.rag.simple_index.search_hybrid`) plus a silent LLM query-expansion network call, and writes the hits into `ir2.metadata["context_snippets"]`. The emitters (`app/emitters.py:509` system prompt, `:672` compact block) render those snippets verbatim into the compiled System Prompt as `#### File: {path}` + fenced content.

Effect: on any machine with a populated local RAG index (e.g. a dev box), **every `compile` leaks local file paths and snippets into the output prompt** — even when irrelevant to the request. This violates the conservative-mode rule ("avoid hallucinated requirements / fake APIs") and pollutes the user-facing prompt. It also fires an unannounced network call.

The CLI `compile` command (`cli/commands/compile_cmd.py:69`, via `_run_compile`) calls `compile_text_v2(full_text)` with no args → default-on → this is the leak the user observed locally. The API v2 path (`api/routes/compile.py:359`, `offline_only=not req.v2`) has the same default-on behavior for v2 requests.

## Root-cause note: `offline_only` is overloaded

`offline_only` currently gates **two** independent things:
- Schema Generator (`app/compiler.py:292`) — offline intelligence.
- Context Strategist / RAG retrieval (`app/compiler.py:323`).

So we must NOT simply flip `offline_only`, which would also kill schema generation. The fix introduces a **dedicated, independent flag** for context retrieval.

## Design (approach C — core default opt-in)

Make RAG/context retrieval **opt-in everywhere**, default off, via a new core parameter. All callers become safe by default; CLI and API opt in explicitly.

### 1. Core — `app/compiler.py`
- Signature: `def compile_text_v2(text: str, offline_only: bool = False, enable_context_retrieval: bool = False) -> IRv2`.
- Change the Context Strategist gate at line 323 from `if not offline_only:` to **`if enable_context_retrieval:`** (decoupled from `offline_only`).
- `offline_only` now gates ONLY the Schema Generator (line 292) — overload resolved.
- **Decision (approved):** gate on `enable_context_retrieval` **alone**, not `enable_context_retrieval and not offline_only`. Rationale: opt-in is an explicit caller choice; local FTS retrieval works offline; query-expansion already fails silently. `offline_only=True` callers never pass the new flag, so they stay off.

### 2. CLI — `cli/commands/compile_cmd.py`
- Add `--rag / --no-rag` Typer option to the `compile` command (and `batch`), **default `False`**.
- Thread it through `_run_compile(...)` → `compile_text_v2(full_text, enable_context_retrieval=rag)`.
- Default off → CLI leak closed. `--rag` lets power users opt in.
- Other CLI call sites (`transform.py:308`, `analytics.py:84`) keep the default (off) — out of scope to expose flags there now.

### 3. API — `api/routes/compile.py`
- Add `enable_context_retrieval: bool = False` to `CompileRequest`.
- Line 359: `compile_text_v2(req.text, offline_only=not req.v2, enable_context_retrieval=req.enable_context_retrieval)`.
- Schema-gen behavior (the `offline_only=not req.v2` part) unchanged. Default off → web/API no longer leak. Response snippet passthrough (`:427`, CriticAgent context) unchanged — degrades gracefully to empty when off.

### 4. Web — no code change
With default off, the "N Sources" badge (`web/app/page.tsx:409`) simply does not render (graceful — that badge was surfacing the leaked context). **Approved:** the web Sources feature goes dormant by default; a UI opt-in toggle is a **separate future task**, out of scope here.

## Testing (TDD — red first)

- **Leak guard (new):** `compile_text_v2(text)` with defaults → Context Strategist not invoked, `context_snippets` absent from metadata, even with a populated index. (Patch `search_hybrid` to assert-not-called.)
- **Opt-in path:** `compile_text_v2(text, enable_context_retrieval=True)` with `search_hybrid` + `_expand_query` mocked → snippets present. (Update existing `tests/test_rag_pipeline.py`, which currently assumes default-on.)
- **Emitter:** no `context_snippets` → System Prompt has no `### Context` section.
- **CLI:** `compile` without `--rag` → output has no Context section; with `--rag` → strategist attempted (mocked).
- **API:** request without flag → response has no context; with flag → context present.

## Out of scope / constraints

- Does NOT touch the larger `#849` repo-context architecture (this is the lite fix; #849 may supersede later).
- No changes to `.env`, providers, LLM prompt format/temperature/max_tokens, deploy config, or dependencies.
- Branch off fresh `origin/main` (local `test/logic-analyzer-coverage` was 14 commits behind, pre core.py split).
- CI gotcha: format changed files with `uvx ruff@0.1.14 check --fix` and `uvx ruff@0.1.14 format` before pushing (Smoke pins ruff 0.1.14).
- Ship as **Draft PR**; manual review of compiled prompt output before merge.
