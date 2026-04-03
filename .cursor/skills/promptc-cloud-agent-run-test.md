# PromptC (Prompt Compiler) — run & test for Cloud agents

Use this skill when you need to **install, run, or verify** this repo locally. There is **no browser “login”**: the backend uses **API keys** (`x-api-key` header) and optional **admin bypass** via env.

---

## Quick setup (repo root: `/workspace` or clone root)

1. **Python 3.10+** — dependencies are defined in `pyproject.toml`.
2. **Install backend + dev/docs extras** (matches CI):

   ```bash
   python -m pip install --upgrade pip
   pip install -e .[dev,docs]
   ```

3. **Environment file** — copy and edit (never commit real keys):

   ```bash
   cp .env.example .env
   ```

4. **Frontend dependencies**:

   ```bash
   cd web && npm ci && cd ..
   ```

---

## Run the app (full stack)

**Terminal 1 — API (default port 8080):**

```bash
python -m uvicorn api.main:app --reload --port 8080
```

**Terminal 2 — Next.js UI (default port 3000):**

```bash
cd web && npm run dev
```

Open `http://localhost:3000`. The UI talks to the API using `NEXT_PUBLIC_API_URL` if set, otherwise `http://127.0.0.1:8080` on local hostnames (see `web/config.ts`).

---

## Auth & API keys (“logging in” for agents)

- **Protected routes** (e.g. `/compile/fast`, generator endpoints, RAG mutations) expect header **`x-api-key`**.
- **Option A — Admin key (stateless):** set `ADMIN_API_KEY` in `.env` to a strong secret; send that value as `x-api-key`. No DB row required.
- **Option B — SQLite keys:** API keys live in `users.db` (path derived from `DB_DIR`, default current directory). Create a key:

  ```bash
  python scripts/create_api_key.py dev-agent
  ```

  Use the printed key as `x-api-key` in `curl` or tools.

- **Browser / Next.js:** for flows that use `buildGeneratorApiHeaders`, set **`NEXT_PUBLIC_API_KEY`** in `web/.env.local` (or env at build time) so the client attaches `x-api-key`. Do not put secrets in committed files.

- **Lock down everything:** `PROMPTC_REQUIRE_API_KEY_FOR_ALL=true` forces key checks broadly (default in `.env.example` is `false` for local dev).

---

## Behavior toggles & “feature flags” (env, not a flag service)

| Variable | Role |
|----------|------|
| `PROMPT_COMPILER_MODE` | `conservative` vs default compiler stance (see README). |
| `PROMPTC_LLM_PROVIDER` | Defaults to **`mock`** — use for tests/no network. Set `openai` (plus keys) for real LLM calls. Related: `PROMPTC_LLM_MODEL`, `PROMPTC_LLM_BASE_URL`, etc. (`app/llm/factory.py`). |
| `OPENAI_API_KEY` / `GROQ_API_KEY` / `OPENAI_BASE_URL` | Real provider access; many code paths error if a live OpenAI call is made without `OPENAI_API_KEY`. |
| `PROMPTC_REQUIRE_API_KEY_FOR_ALL` | `true`/`1`/`yes`/`on` = require API key on routes that use `verify_api_key_if_required`. |
| `PROMPTC_UPLOAD_DIR` | RAG upload storage directory. |
| `PROMPTC_RAG_ALLOWED_ROOTS` | Comma-separated allowlist roots for path-based ingest (tests patch this). |
| `DB_DIR` | Where `users.db` is created. |
| `JULES_API_KEY` | Jules integration; missing key → configuration/runtime errors on those paths. |

**Mocking LLMs in automated tests:** prefer `PROMPTC_LLM_PROVIDER=mock`, `unittest.mock.patch`, or offline-only compiler paths — follow patterns in `tests/`.

---

## Testing by area

### Backend — `api/`, `app/`, `cli/`

- **Full suite (what CI runs on non-PR branches):**

  ```bash
  pytest -q --cov=app --cov=cli --cov=api --cov-report=term-missing
  ```

- **PR smoke subset (fast, matches `.github/workflows/ci.yml`):**

  ```bash
  pytest -q \
    tests/test_api_hardening.py \
    tests/test_auth_fast_path.py \
    tests/test_rag_upload.py \
    tests/test_benchmark_api.py
  ```

- **Auth tests:** `tests/conftest.py` **overrides** API auth for most modules. `tests/test_auth_fast_path.py` and tests marked `@pytest.mark.auth_required` run **without** that override — do not assume global auth bypass applies there.

- **Repo hygiene (CI):**

  ```bash
  pre-commit run --all-files --show-diff-on-failure
  pip check
  ```

### Frontend — `web/`

```bash
cd web
npm run test:contracts   # Node built-in tests: config + API contracts
npm run lint
npm run build
```

`npm run dev` for manual UI verification against a running API.

### VS Code extension — `integrations/vscode-extension/`

Requires a running API (`promptc.apiBaseUrl`, default `http://127.0.0.1:8080`). Extension stores API keys in **VS Code secret storage**, not repo files.

```bash
cd integrations/vscode-extension
node --test tests/client.test.mjs
```

### CLI smoke

Entry point: `promptc` (from `[project.scripts]`). Quick check:

```bash
promptc --help
```

Targeted tests: `tests/test_cli_*.py`, `tests/test_github_artifacts.py`, etc.

---

## Updating this skill

When you discover new setup steps, env vars, ports, or test commands:

1. **Change the code or CI first**, then update this file to match — README and `.github/workflows/ci.yml` are authoritative for install and smoke commands.
2. Add **concrete commands** (copy-pasteable), not vague prose.
3. If a new **env toggle** affects behavior or tests, add one line to the behavior table and mention **where it is read** in code if non-obvious.
4. Keep sections **by area** (`api`/`app`, `web`, `integrations/vscode-extension`, `cli`) so the next agent can jump to the right workflow.
