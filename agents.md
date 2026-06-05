# Cloud Agent Starter Skill — Prompt Compiler

This file is read automatically by Cursor Cloud agents at the start of every session.
It tells agents exactly how to set up, run, and test this codebase.
Keep it up to date as you discover new workflows, debugging tricks, or environment quirks.

---

## 1. Quick-Start Checklist

Run these steps once at the start of any Cloud agent session before touching code.

```bash
# 1. Install backend (source of truth: pyproject.toml)
pip install -e .[dev,docs]

# 2. Install frontend
cd web && npm ci && cd ..

# 3. Verify environment file exists (copy from template if missing)
[ -f .env ] || cp .env.example .env
```

You do **not** need to commit `.env`. It is gitignored and only needed for local runs.

---

## 2. Environment Variables

`.env.example` is the canonical list. Copy it and fill in secrets before starting the app.

| Variable | Required for | Default / Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | LLM compile, optimize, benchmark | No default — must be set for cloud LLM paths |
| `OPENROUTER_BASE_URL` | LLM provider URL | `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | Default cloud model slug | `openai/gpt-oss-20b` |
| `LLM_AGENT_MAX_TOKENS` | Agent generator response cap | `2048`; lower it to reduce token usage or raise it for longer generated packs |
| `LLM_SKILL_MAX_TOKENS` | Skill generator response cap | `2048`; mirrors the agent cap for MCP/skill output generation |
| `PROMPT_COMPILER_MODE` | Compiler aggressiveness | `conservative` (default) or `default` |
| `ADMIN_API_KEY` | Legacy/internal master API key (skip DB lookup where auth helpers are still used) | Optional; not required for the public app |
| `PROMPTC_REQUIRE_API_KEY_FOR_ALL` | Legacy/internal auth toggle | Public app routes should not depend on this |
| `DB_DIR` | Where `users.db` is written | `.` (repo root) |
| `PROMPTC_UPLOAD_DIR` | RAG file upload directory | `~/.promptc_uploads` |
| `PROMPTC_RAG_DB_PATH` | RAG SQLite index path | Empty = `~/.promptc_index_v3.db`; if that path is not writable, runtime falls back to `./.promptc/<db-name>` |
| `PROMPTC_RAG_ALLOWED_ROOTS` | Path allowlist for RAG ingest | Empty = restricted to CWD + upload dir |
| `NEXT_PUBLIC_API_URL` | Frontend → backend URL | `http://127.0.0.1:8080` |
| `ALLOWED_ORIGINS` | CORS origin list (comma-separated) | Defaults to localhost:3000/3001 |
| `PORT` | Uvicorn port (Docker/Fly) | `8000` |

### Minimal `.env` for local dev (no LLM calls needed for most tests)

```env
PROMPT_COMPILER_MODE=conservative
PROMPTC_REQUIRE_API_KEY_FOR_ALL=false
DB_DIR=.
NEXT_PUBLIC_API_URL=http://127.0.0.1:8080
```

### Auth / API key notes

- Public app routes are intended to work **without** asking visitors for a Prompt Compiler API key.
- Cloud-backed features may still need a server-side provider credential such as `OPENROUTER_API_KEY`, but that stays on the server and is never typed by end users.
- OpenRouter is the **only** supported cloud provider for this repo. Do not reintroduce Groq or OpenAI fallbacks into public product flows, defaults, or docs.
- `x-api-key`, `PROMPTC_SERVER_API_KEY`, and similar custom backend keys are legacy/internal mechanisms and should not be introduced into public web flows.
- In tests, authentication is **automatically bypassed** by `conftest.py` unless the test is marked `@pytest.mark.auth_required`.

### Mocking / disabling LLM calls

The codebase is designed so that offline heuristics in `app/heuristics/` run without any LLM key. Set `PROMPT_COMPILER_MODE=conservative` and simply omit `OPENROUTER_API_KEY`; the compiler falls back to local heuristics for most operations. Test files under `tests/` do the same — no live LLM calls are made.

If agent-pack or skill exports are getting truncated, adjust `LLM_AGENT_MAX_TOKENS` or `LLM_SKILL_MAX_TOKENS` in `.env` before retrying.

---

## 3. Starting the Application

Two processes must run together: the FastAPI backend and the Next.js frontend.

```bash
# Terminal 1 — backend (auto-reload)
python -m uvicorn api.main:app --reload --port 8080

# Terminal 2 — frontend dev server
cd web && npm run dev
```

Open http://localhost:3000 in a browser.

Frontend routes use same-origin Next proxy handlers so the browser never needs a backend secret. Do not add browser API-key inputs or server-proxy key requirements for public usage.

Backend is available at http://127.0.0.1:8080 and exposes an OpenAPI spec at http://127.0.0.1:8080/docs.

### Production-style run (single process, no reload)

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Fly.io operational note

- `mycompiler-api` has proven too tight at `256mb` on Fly Machines for generator/RAG-backed requests. Treat `512mb` as the minimum practical production memory size unless profiling proves otherwise.
- Keep `min_machines_running = 1` for `mycompiler-api` in production. Letting the only machine scale down to zero causes cold-start races where Next proxy routes can return a fast 502 before Uvicorn is reachable, especially on `/compile` and `/agent-packs/claude`.
- When Fly emails an `OOM: uvicorn killed` alert, check the current machine and recent logs first:

```bash
fly status -a mycompiler-api
fly logs -a mycompiler-api --no-tail
```

### Docker

```bash
docker build -t promptc .
docker run -p 8000:8000 --env-file .env promptc
```

No `docker-compose` file exists; start auxiliary services manually if needed.

---

## 4. Feature Flags & Behavior Toggles

There is no runtime feature-flag system (no LaunchDarkly, no flag DB). All toggles are environment variables or per-request parameters.

| Toggle | How to set | Effect |
|---|---|---|
| Conservative mode | `PROMPT_COMPILER_MODE=conservative` (env), `"mode": "conservative"` in request body, or `X-Prompt-Mode: conservative` header | Compiler stays grounded; no hallucinated context |
| Default / aggressive mode | `PROMPT_COMPILER_MODE=default` | Compiler fills gaps and expands more aggressively |
| Legacy/internal auth toggle | `PROMPTC_REQUIRE_API_KEY_FOR_ALL=true` | Only affects routes that still opt into auth helpers; public app routes should not rely on it |
| CORS restriction | Set `ALLOWED_ORIGINS=https://yourdomain.com` | Restricts which origins the backend accepts |

**UI toggle**: the web app has a "Conservative" toggle stored in `localStorage` (key `promptc_conservative_mode`). The browser extension has its own local state. For automated tests, control the mode through the API request body directly.

**To test non-conservative mode in isolation**, set `PROMPT_COMPILER_MODE=default` in `.env` before starting the server, or override it in individual test parametrize calls.

---

## 5. Codebase Areas and Testing Workflows

### 5.1 Backend — Core Compiler (`app/`)

Relevant files: `app/compiler.py`, `app/emitters.py`, `app/models_v2.py`, `app/heuristics/`, `app/llm_engine/`

**Run all compiler-related tests:**

```bash
pytest tests/ -q --ignore=tests/test_api_hardening.py --ignore=tests/test_auth_fast_path.py
```

**Run a focused subset (fast, no LLM):**

```bash
pytest tests/test_offline_mode.py tests/test_offline_advanced.py tests/test_heuristics_regex_safety.py tests/test_conservative_mode.py -v
```

**Run with coverage report:**

```bash
pytest --cov=app --cov=cli --cov=api --cov-report=term-missing tests/ -q
```

**Key test markers:**

```bash
# Tests that actually exercise real auth (no autouse override)
pytest -m auth_required -v
```

**What to check when modifying `app/compiler.py`:**

- Run `tests/test_determinism.py` to ensure the same input always gives the same output class.
- Run `tests/test_snapshot.py` to catch unintended output regressions.
- Run `tests/test_safety.py` and `tests/test_adversarial.py` to verify guardrails still hold.

---

### 5.2 Backend — FastAPI Routes (`api/`)

Relevant files: `api/main.py`, `api/auth.py`, `api/routes/`, `api/shared.py`

**CI smoke test (fast gate — run before every push):**

```bash
pytest -q \
  tests/test_api_hardening.py \
  tests/test_auth_fast_path.py \
  tests/test_rag_upload.py \
  tests/test_benchmark_api.py
```

**Test all API routes:**

```bash
pytest tests/test_compile_policy_api.py tests/test_agent_generator.py tests/test_skills_generator.py tests/test_optimize_api.py tests/test_benchmark_api.py tests/test_rag_upload.py tests/test_security_headers.py -v
```

**Live optimizer tests (opt-in only; requires upstream credentials):**

```bash
OPENROUTER_API_KEY=... pytest tests/optimizer/test_optimize_live.py --run-live -m live -v
```

**Live API smoke test (requires running backend):**

```bash
# Health check
curl http://127.0.0.1:8080/health

# Root info
curl http://127.0.0.1:8080/

# Compile
curl -s -X POST http://127.0.0.1:8080/compile \
  -H "Content-Type: application/json" \
  -d '{"text": "summarize a PDF and write a report", "mode": "conservative"}' | python -m json.tool

# Compile fast
curl -s -X POST http://127.0.0.1:8080/compile/fast \
  -H "Content-Type: application/json" \
  -d '{"text": "create a marketing email", "mode": "default"}' | python -m json.tool
```

**Auth testing — bypass vs. enforce:**

```bash
# Test without override (real auth check)
pytest tests/test_auth_fast_path.py -v

# Public routes should remain callable even if legacy/internal auth flags are present
PROMPTC_REQUIRE_API_KEY_FOR_ALL=true pytest tests/test_auth_fast_path.py -v
```

**Adding a new route:** follow `api/routes/compile.py` as the template. Always add a Pydantic request model, apply `Depends(verify_api_key)` or `Depends(verify_api_key_if_required)`, and cover it in a new test file.

---

### 5.3 Backend — RAG (`app/rag/`)

Relevant files: `app/rag/simple_index.py`, `api/routes/rag.py`

**RAG-specific tests:**

```bash
pytest tests/test_rag.py tests/test_rag_upload.py tests/test_rag_pipeline.py tests/test_rag_chunking.py tests/test_rag_hybrid_api.py tests/test_rag_parsers.py -v
```

**Windows temp-dir note:** `tests/conftest.py` now prefers a repo-local `.\.tmp-test-run` session dir and falls back to a user temp folder automatically if that repo-local runtime root is not writable. `tests/runtime_bootstrap.py` creates the pytest session directory directly under the candidate root, probes both a simple child folder and a pytest-style nested temp tree before use, and points `TMP`/`TEMP`/`TMPDIR` at a dedicated `tmp` child inside that session so ad-hoc `tempfile` directories do not collide with pytest's own `pytest-of-*` folders on Windows. If you still hit a `PermissionError`, inspect stale directories under `.\.tmp-test-run` first, then override `TMP`, `TEMP`, and `DB_DIR` manually only as a last resort.

**RAG upload smoke (requires running backend):**

```bash
# Upload a file (JSON body: filename, content, optional relative_path)
curl -s -X POST http://127.0.0.1:8080/rag/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "README.md", "content": "your file content here"}' | python -m json.tool

# Search (POST with JSON body: query, limit)
curl -s -X POST http://127.0.0.1:8080/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "compiler", "limit": 3}' | python -m json.tool
```

**Path security:** RAG ingest (`/rag/ingest`) validates against `PROMPTC_RAG_ALLOWED_ROOTS`. If left empty, access is restricted to the current working directory plus the upload directory (`~/.promptc_uploads`). For security tests, set it to a specific temp dir.

---

### 5.4 Frontend — Next.js (`web/`)

Relevant files: `web/app/`, `web/app/components/`, `web/app/hooks/`

**Contract tests (fast, no browser needed):**

```bash
cd web && npm run test:contracts
```

**Frontend unit tests (Vitest):**

```bash
cd web && npm run test
```

**Lint:**

```bash
cd web && npm run lint
```

**Build check (catches TypeScript errors):**

```bash
cd web && npm run build
```

**Manual UI testing** requires the backend running on port 8080 and the dev server on port 3000. All pages:

| Page | Path |
|---|---|
| Main compiler | http://localhost:3000 |
| Agent Generator | http://localhost:3000/agent-generator |
| Skill Generator | http://localhost:3000/skills-generator |
| Benchmark | http://localhost:3000/benchmark |
| Token Optimizer | http://localhost:3000/optimizer |
| Offline / heuristics | http://localhost:3000/offline |

---

### 5.5 CLI (`cli/`)

Relevant files: `cli/main.py`

**Run CLI directly (no install):**

```bash
python -m cli.main --help
python -m cli.main compile "summarize this PDF for a non-technical audience"
python -m cli.main github render --type pr-review-brief --from-file prompt.txt
```

**After `pip install -e .`, use the `promptc` shorthand:**

```bash
promptc --help
promptc compile "build a login flow for a FastAPI app"
```

**CLI tests:**

```bash
pytest tests/test_cli_console_refactor.py tests/test_cli_new_features.py tests/test_cli_extras.py -v
```

---

### 5.6 Integrations

**VS Code extension** (`integrations/vscode-extension/`): install deps with `cd integrations/vscode-extension && npm ci`. Open the folder in VS Code and press F5 (or use `.vscode/launch.json`) to launch the extension development host. Requires a running backend. Automated checks:

```bash
cd integrations/vscode-extension
npm run test:unit
npm run test:integration
npm run package
```

**MCP server** (`integrations/mcp-server/`): install its own requirements (`pip install -r integrations/mcp-server/requirements.txt`) and run with:

```bash
python integrations/mcp-server/server.py
```

**Browser extension** (`extension/`): load as an unpacked extension in Chrome from `extension/` directory. Test files (`*.test.mjs`) can be run with Node:

```bash
node --test extension/*.test.mjs
```

### 5.7 Repo Hygiene (`scripts/`)

Use branch/worktree cleanup audit script before large PR triage or manual cleanup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/branch_audit.ps1 -IncludeDeleteCommands
```

---

## 6. Linting and Code Style

```bash
# Auto-fix and format Python (ruff)
ruff check --fix .
ruff format .

# Run the full pre-commit suite (same as CI)
pre-commit run --all-files

# Frontend lint
cd web && npm run lint
```

Line length limit: **120** characters (see `ruff.toml`).
Style: Conventional Commits for commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

---

## 7. CI Gate Summary

CI runs on every PR. It must pass before merge. Reproduce it locally with:

```bash
# Step 1: Python smoke tests
pip check

# Step 2: Python smoke tests
pytest -q \
  tests/test_api_hardening.py \
  tests/test_auth_fast_path.py \
  tests/test_rag_upload.py \
  tests/test_benchmark_api.py

# Step 3: Pre-commit (linting + formatting)
pre-commit run --all-files

# Step 4: Frontend
node --test extension/*.test.mjs

cd web
npm ci
npm run test:contracts
npm run test
npm run lint
npm run build
cd ..

# Step 5: VS Code extension
cd integrations/vscode-extension
npm ci
npm run test:unit
npm run test:integration
npm run package
cd ../..
```

Full matrix tests (Python 3.10–3.12, Linux/Windows/macOS) only run on push to `main`, not on PRs.

### Snyk dependency scan

The dedicated GitHub workflow in `.github/workflows/snyk.yml` scans `requirements.txt` and `pyproject.toml`
explicitly with separate `snyk test --file=...` commands. Keep the runtime dependency snapshot in
`requirements.txt` aligned with `pyproject.toml`, and avoid adding editable-install-only packages to the Snyk job
because that can create noisy dependency graphs and stale vulnerability alerts.

---

## 8. Security Rules (Non-Negotiable)

Summarized from `agents.md` — read that file for full detail.

- **Never** accept raw file paths from user input. Always resolve and anchor to an allowed root using `Path.resolve()`.
- **Never** concatenate user input into SQL strings. Use parameterized queries.
- **Never** log or return environment variables, API keys, or DB credentials.
- **Never** hardcode secrets. Use `.env` / environment variables.
- All new FastAPI endpoints must: validate input with Pydantic, apply appropriate `Depends(verify_api_key*)`, handle exceptions gracefully, and not leak stack traces.
- Generated code from Agent/Skill generators must be treated as untrusted if ever executed.

---

## 9. Updating This Skill

When you discover a new testing trick, a debugging workaround, a common failure mode, or a runbook step that would help the next agent, **update this file immediately** as part of that same PR.

Guidelines for updates:

- Add new env variables to the table in Section 2 as soon as you discover them.
- Add new curl examples or pytest invocations to the relevant area section in Section 5.
- If a CI step changes (new command, new test file added to the smoke gate), update Section 7.
- If a new integration or codebase area is added (new route group, new CLI subcommand, new `web/app/` page), add a subsection under Section 5.
- Keep sections concise. Prefer concrete commands over prose explanations.
- If a known issue or workaround exists (e.g., a test that must be skipped in certain environments), note it inline where it first appears.

Commit format for skill updates: `docs: update AGENTS.md — <one-line description of what changed>`
