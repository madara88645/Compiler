# Repo Context Layer Design

## Problem

Compiler has two separate context paths today:

- Generator pages can analyze a public GitHub repository and pass a shallow repo brief into the agent/skill LLM call.
- Compile v2 can auto-retrieve local RAG snippets and render them into prompts.

Those paths are not feature-agnostic, and the compile path can leak local absolute paths from a populated RAG index into rendered prompts. Repo context needs one shared, explicit, path-safe shape that every feature can consume.

## Goals

- Provide one `RepoContextEnvelope` for GitHub brief, RAG index, local upload, and future manual context sources.
- Keep context opt-in for compile and generators; no automatic local RAG injection by default.
- Preserve the existing `/repo-context/github` public response shape for compatibility.
- Render LLM context through one path-safe renderer.
- Keep PR Safety behavior unchanged while leaving a typed future entry point.

## Non-Goals

- No local clone crawler in this PR.
- No GitHub PR fetch or GitHub App behavior in this PR.
- No provider, prompt, temperature, response format, dependency, auth, DB, secret, or deploy changes.
- No `cli/` changes.

## Interface

`RepoContextEnvelope` is the internal cross-feature format:

- `source_type`: `github_public`, `rag_index`, `local_upload`, or `manual`
- `repo_identity`: repo name, URL, default branch, optional ref
- `summary`: full and compact text
- `detected_stack`: short stack signals
- `files_used`: safe display paths only
- `snippets`: safe display path, content, score, source label
- `budget`: max chars, used chars, truncated
- `safety`: path-safe booleans

The existing `GitHubRepoContextPayload` remains the API compatibility wrapper for `/repo-context/github` and existing generator UI requests.

## Behavior

- GitHub repo analysis still returns the legacy top-level JSON payload.
- Generator requests normalize any supplied legacy repo payload into `RepoContextEnvelope` before calling the worker.
- Compile accepts optional `repo_context`; when omitted, no RAG/repo context is attached.
- RAG results are only used when explicitly supplied and are normalized into safe display paths.
- Rendered LLM context must not include `/Users/...`, `/home/...`, `~/...`, or Windows drive absolute paths.

## Risks

- Existing tests that assumed auto-RAG need to be updated to the new opt-in contract.
- Cached compile results must include repo-context fingerprint when context is supplied.
- The legacy GitHub response must remain stable so current UI does not break.
