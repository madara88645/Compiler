# Repo Context Layer Implementation Plan

## Summary

Add a shared repo-context module, route existing GitHub generator context through it, and stop default compile/RAG context injection. Keep public API behavior stable while ensuring LLM-rendered context is path-safe and opt-in.

## Implementation Steps

1. Add `app/repo_context/` with shared Pydantic models, source adapters, path sanitizer, and `render_repo_context_for_llm()`.
2. Move the generator route's legacy `GitHubRepoContextPayload` model to the shared module and re-export it from `api.routes.generators`.
3. Replace `WorkerClient._render_repo_context_block()` body with the shared renderer.
4. Update `HybridCompiler.compile()`, `generate_agent()`, and `generate_skill()` so repo/RAG context is attached only when explicitly supplied.
5. Update `compile_text_v2()` and `/compile` to accept optional `repo_context`; attach the normalized envelope into IR metadata for rendered prompt output.
6. Update emitters and compile critique context to render repo/RAG context through the shared path-safe renderer.
7. Add/update tests for GitHub normalization, RAG path sanitization, compact/full rendering, compile no-auto-RAG, explicit context, and API backwards compatibility.

## Validation

- `pytest tests/test_repo_context_layer.py tests/test_context_generation.py tests/test_rag_pipeline.py tests/test_hybrid.py -q`
- `pytest tests/test_repo_context.py tests/test_generators.py tests/test_pr_safety_api.py -q`
- `cd web && npm run test -- agent-generator/page.test.tsx skills-generator/page.test.tsx`

## Safety Notes

- No `cli/` edits.
- No `.env`, secrets, auth, DB, deploy config, dependency, model, provider, temperature, max token, or response-format changes.
- First PR should be draft because it touches shared context flow and prompt rendering.
