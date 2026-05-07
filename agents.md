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
| `OPENAI_API_KEY` | LLM compile, optimize, benchmark | No default — must be set for LLM paths |
| `OPENAI_BASE_URL` | LLM provider URL | `https://api.openai.com` |
| `GROQ_API_KEY` | Groq-backed LLM paths | Optional; LLM routes fall back to OpenAI |
| `PROMPT_COMPILER_MODE` | Compiler aggressiveness | `conservative` (default) or `default` |
| `ADMIN_API_KEY` | Master API key (skip DB lookup) | Optional; leave blank for local dev |
| `PROMPTC_REQUIRE_API_KEY_FOR_ALL` | Force API keys everywhere | `false` for local dev, `true` for hardened deploys |
| `DB_DIR` | Where `users.db` is written | `.` (repo root) |
| `PROMPTC_UPLOAD_DIR` | RAG file upload directory | `~/.promptc_uploads` |
| `PROMPTC_RAG_DB_PATH` | RAG SQLite index path | Empty = `~/.promptc_index_v3.db`; if that path is not writable, runtime falls back to `./.promptc/<db-name>` |
| `NEXT_PUBLIC_API_KEY` | Frontend API key for authenticated requests | Optional; injected as `x-api-key` header by `buildGeneratorApiHeaders` |
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

- Most routes accept any request locally when `PROMPTC_REQUIRE_API_KEY_FOR_ALL=false`.
- Routes that **always** require an API key: `/compile/fast`, all `/agent-generator/*`, `/skills-generator/*`, and `/rag/upload`, `/rag/ingest`. Other RAG endpoints (`/rag/query`, `/rag/pack`, `/rag/search`, `/rag/stats`) use `verify_api_key_if_required` and are optional unless `PROMPTC_REQUIRE_API_KEY_FOR_ALL=true`.
- To make an authenticated request, add header `x-api-key: <key>`.
- In tests, authentication is **automatically bypassed** by `conftest.py` — no key needed unless the test is marked `@pytest.mark.auth_required`.

### Mocking / disabling LLM calls

The codebase is designed so that offline heuristics in `app/heuristics/` run without any LLM key. Set `PROMPT_COMPILER_MODE=conservative` and simply omit `OPENAI_API_KEY` / `GROQ_API_KEY`; the compiler falls back to local heuristics for most operations. Test files under `tests/` do the same — no live LLM calls are made.

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

Backend is available at http://127.0.0.1:8080 and exposes an OpenAPI spec at http://127.0.0.1:8080/docs.

### Production-style run (single process, no reload)

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
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
| Global API key enforcement | `PROMPTC_REQUIRE_API_KEY_FOR_ALL=true` | Every route requires `x-api-key` |
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
GROQ_API_KEY=... pytest tests/optimizer/test_optimize_live.py --run-live -m live -v
```

**Live API smoke test (requires running backend):**

```bash
# Health check
curl http://127.0.0.1:8080/health

# Root info
curl http://127.0.0.1:8080/

# Compile (no API key needed with PROMPTC_REQUIRE_API_KEY_FOR_ALL=false)
curl -s -X POST http://127.0.0.1:8080/compile \
  -H "Content-Type: application/json" \
  -d '{"text": "summarize a PDF and write a report", "mode": "conservative"}' | python -m json.tool

# Compile fast (requires API key)
curl -s -X POST http://127.0.0.1:8080/compile/fast \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-key" \
  -d '{"text": "create a marketing email", "mode": "default"}' | python -m json.tool
```

**Auth testing — bypass vs. enforce:**

```bash
# Test without override (real auth check)
pytest tests/test_auth_fast_path.py -v

# See what happens with PROMPTC_REQUIRE_API_KEY_FOR_ALL=true
PROMPTC_REQUIRE_API_KEY_FOR_ALL=true pytest tests/test_api_hardening.py -v
```

**Adding a new route:** follow `api/routes/compile.py` as the template. Always add a Pydantic request model, apply `Depends(verify_api_key)` or `Depends(verify_api_key_if_required)`, and cover it in a new test file.

---

### 5.3 Backend — RAG (`app/rag/`)

Relevant files: `app/rag/simple_index.py`, `api/routes/rag.py`

**RAG-specific tests:**

```bash
pytest tests/test_rag.py tests/test_rag_upload.py tests/test_rag_pipeline.py tests/test_rag_chunking.py tests/test_rag_hybrid_api.py tests/test_rag_parsers.py -v
```

**Windows temp-dir note:** `tests/conftest.py` now prefers a repo-local `.\.tmp-test-run` session dir and falls back to a user temp folder automatically if that repo-local runtime root is not writable. If you still hit a `PermissionError`, inspect stale directories under `.\.tmp-test-run` first, then override `TMP`, `TEMP`, and `DB_DIR` manually only as a last resort.

**RAG upload smoke (requires running backend and an API key):**

```bash
# Upload a file (JSON body: filename, content, optional relative_path)
curl -s -X POST http://127.0.0.1:8080/rag/upload \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-key" \
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

**VS Code extension** (`integrations/vscode-extension/`): no automated tests. Open the folder in VS Code and press F5 to launch the extension development host. Requires a running backend.

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
```

Full matrix tests (Python 3.10–3.12, Linux/Windows/macOS) only run on push to `main`, not on PRs.

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
