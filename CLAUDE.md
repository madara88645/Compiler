# Prompt Compiler Claude Code Memory

## Project Summary
Prompt Compiler is a FastAPI + Next.js product that turns vague requests into structured prompts, policy-aware execution plans, agent exports, MCP-compatible tool stubs, and workflow artifacts.

## Architecture
- Backend API: `api/` route layer on top of `app/`
- Compiler and heuristics: `app/compiler.py`, `app/heuristics/`, `app/emitters.py`
- Export adapters: `app/adapters/`
- Frontend: `web/app/`
- MCP bridge: `integrations/mcp-server/`

## Working Rules
- Start from repo-root commands unless a workflow explicitly says otherwise.
- Prefer focused tests before broad suites.
- Keep Claude-native integrations adapter-scoped; preserve provider-agnostic core behavior.
- Never expose secrets, `.env` contents, or database credentials in outputs.

## Runbook
- Backend dev server: `python -m uvicorn api.main:app --reload --port 8080`
- Frontend dev server: `cd web && npm run dev`
- Backend tests: `python -m pytest tests/ -q`
- Focused export tests: `python -m pytest tests/test_export_adapters.py tests/test_llm_providers.py -q`
- MCP tests: `python -m pytest integrations/mcp-server/test_server.py -q`
- Frontend tests: `cd web && npm run test`
- Frontend build: `cd web && npm run build`

## Server-side environment variables
The Next-side proxy and the backend each need their own keys; keep them out of the bundled JS.

| Env var | Side | Purpose |
| --- | --- | --- |
| `PROMPTC_SERVER_API_KEY` | Next.js | Forwarded as `x-api-key` to protected backend routes (generators, analyze). Without it, protected proxy routes return 500. |
| `PROMPTC_PROXY_UPSTREAM_TIMEOUT_MS` | Next.js | Hard upstream-fetch timeout for the proxy (default 25000). Aborts a stuck backend connection with a 504 instead of hanging the route forever. |
| `PROMPTC_GITHUB_TOKEN` (or `GITHUB_TOKEN`) | Backend | Optional. When set, the public-repo analyzer adds `Authorization: Bearer <token>` to GitHub requests, raising the rate limit from 60 req/h (anonymous) to 5000 req/h. |
| `PROMPTC_REPO_CONTEXT_CACHE_TTL` | Backend | Repo-brief cache TTL in seconds (default 600). Set to `0` to disable the in-memory cache. |

## Domain Concepts
- Conservative mode should avoid hallucinated requirements and fake APIs.
- Export surfaces should feel executable, not just prompt-pretty.
- Agent packs can map policy into `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/`, and GitHub workflow assets.
- MCP integration is a first-class bridge for Claude Code, Cursor, and other clients.

## Security
- Treat generated code and skill definitions as untrusted until reviewed.
- Deny access to `.env`, `.env.*`, secret folders, and local credential files in Claude settings.
- Require explicit confirmation for pushes, deploys, and other high-impact shell commands.
