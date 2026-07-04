# Agent Packs → Repo-Aware MCP Initializer (Slice B1) — Design

- **Date:** 2026-07-03
- **Status:** Approved (design), pending spec review → implementation plan
- **Scope (B1):** Backend core (`app/`) + MCP bridge (`integrations/mcp-server/`). **No web changes in B1.**

## Goal

Make Agent Packs genuinely functional — "like `claude /init`, but better." The essence of
`/init` is **repo awareness**: it inspects the actual codebase. Today Agent Packs generates
from three free-text fields and never sees the repo, so output is generic and delivery is a
manual download-and-place chore. B1 delivers a repo-aware initializer that runs **inside the
repo via an MCP tool**, reads real project facts, and applies the pack with a
**preview → confirm → write** safety model.

## Context (confirmed by code map)

- **The backend generator is already real**, not placeholder: `app/adapters/agent_packs.py`
  → `app/adapters/claude_code.py` runs the compiler and emits correct Claude-native files
  (valid `.claude/settings.json`, a working `anthropics/claude-code-action` `.github/workflows/claude.yml`,
  subagent `.md` files with valid YAML frontmatter). Served via `POST /agent-packs/claude`
  (manifest JSON) and `POST /agent-packs/claude/download` (single file or zip).
- **Why it feels non-functional:**
  1. **No repo awareness** — inputs are free-text `project_type` / `stack` / `goal`; it never
     reads `package.json`, `pyproject.toml`, an existing `CLAUDE.md`, or real test/build commands.
     The generated "Validation contract" even tells the *user* to discover commands because the
     generator can't.
  2. **No apply path** — output is a zip the user must unzip and hand-place.
  3. Inert checklist, a dead provider card (no `onClick`), heavy "beta/experimental" hedging. *(B2)*
  4. **Bug:** `risk_mode` strict vs balanced produces an **identical** `settings.json` and
     `permission_mode` ("acceptEdits"), yet the UI claims "tighter permissions."
  5. Computed IR fields (`hook_suggestions`, `mcp_servers`, `memory_outline`, …) are produced
     in `app/adapters/agent_ir.py` but never rendered into any emitted file — dead output. *(B3)*

## Locked Decisions

- **Vehicle:** MCP tool in `integrations/mcp-server/` (Python; runs locally with filesystem access).
- **Safety:** preview → confirm → write. Existing files are **never silently overwritten**.
- **B1 = MCP + backend only.** Web page untouched (its polish is B2).
- **Existing `CLAUDE.md`:** do not clobber — surface a diff in the plan; on apply, either add a
  managed section or write `.new` alongside. Never overwrite without it appearing in the plan.
- **Fix the `risk_mode` bug in B1** so the generated `settings.json` is honest.

## Architecture (B1)

### 1. New core — `app/repo_inspect/` (pure, provider-agnostic, unit-testable)

Given a repo path, produce a `RepoContext`:
- **Stack detection:** `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`,
  `Cargo.toml`, etc. → languages + frameworks.
- **Real commands:** test / build / lint / dev from `package.json` scripts, `Makefile`,
  `pyproject.toml` (so the pack states real commands instead of "discover them").
- **Existing config:** contents of any existing `CLAUDE.md` and `.claude/` files (for diffing/merge).
- **Directory map:** a shallow tree of top-level structure.

`RepoContext` is the single artifact that closes the repo-blindness gap and is reusable by a
future CLI (B3) or web upload path.

### 2. Generation — reuse the existing engine

Do **not** rewrite `app/adapters/*`. Feed `RepoContext` into the existing request/generator so
the emitted files use real detected facts. Concretely: extend the pack request with optional
repo-derived fields (detected stack string, real commands, existing-config awareness) and thread
them into `claude_code.py` emitters (esp. the CLAUDE.md "Validation contract" and settings).

### 3. MCP tools (in `integrations/mcp-server/`)

- **`plan_agent_pack(pack_type, goal?, risk_mode?, path=".")`** — read-only. Inspects the repo,
  generates the manifest, computes a **diff vs existing files**, and returns a structured plan:
  files to create, files that would conflict (with diffs), detected stack/commands, and the
  readiness verdict. Nothing is written.
- **`apply_agent_pack(pack_type, goal?, risk_mode?, path=".", overwrite?=[])`** — writes files.
  New files are created at correct paths (`CLAUDE.md`, `.claude/…`, `.github/workflows/…`).
  A path that already exists is **only** overwritten if it appears in the explicit `overwrite`
  list (which the plan surfaces); otherwise it is written as `<path>.new` and reported. This
  realizes preview → confirm → write.

**Plan-time verification:** confirm how the current MCP server obtains generation — direct
`import` of `app.adapters` (preferred, since server and app share the repo) vs calling the HTTP
API. `repo_inspect` must run in the local MCP process regardless (it needs the filesystem);
generation may reuse `app` locally or via API. Pick the path that matches the existing server.

### 4. Fix `risk_mode` → `settings.json`

In `app/adapters/claude_code.py` (the hardcoded `settings.json` builder, ~lines 267–289, and
`permission_mode`): make **strict** produce a genuinely tighter policy (broader `deny`, more
`ask`-gated commands, and a stricter `permission_mode`) than **balanced**. The UI's "tighter
permissions" claim must become true. Covered by tests asserting strict ≠ balanced.

## Decomposition

- **B1 (this spec):** `app/repo_inspect/`, repo-aware generation, `plan_agent_pack` /
  `apply_agent_pack` MCP tools, `risk_mode` fix.
- **B2 (later):** Web page polish — interactive checklist, real file-tree preview with per-file
  download, remove/w­ire the dead provider card, reduce beta hedging, package download from
  in-state manifest.
- **B3 (later):** Render dead IR fields (`hook_suggestions` → settings hooks, `mcp_servers` →
  `.mcp.json`), smart `CLAUDE.md` merge, CLI and GitHub-PR vehicles.

## Testing

- `app/repo_inspect/`: unit tests over fixture repos (node-only, python-only, mixed, empty,
  pre-existing `CLAUDE.md`/`.claude/`) asserting detected stack, commands, and config.
- `risk_mode`: assert strict and balanced produce different `settings.json` / `permission_mode`.
- MCP tools (`integrations/mcp-server/test_server.py`): `plan_agent_pack` writes nothing and
  returns a plan with diffs; `apply_agent_pack` creates new files, does **not** overwrite an
  existing file unless listed in `overwrite`, and writes `.new` on conflict.
- Keep provider-agnostic core behavior intact (OpenRouter-only cloud rule unchanged; no new
  end-user API-key requirements).

## Non-Goals (B1)

- No web/frontend changes.
- No new cloud provider, no end-user API-key prompts (per project rules).
- No GitHub integration, no standalone CLI (B3).
- Not rendering the currently-dead IR fields (B3).

## Files

- **New:** `app/repo_inspect/` (module + tests); new MCP tool handlers in `integrations/mcp-server/`.
- **Modified:** `app/adapters/agent_packs.py`, `app/adapters/claude_code.py` (repo-aware inputs +
  `risk_mode` fix), possibly `app/adapters/agent_ir.py` (thread real commands), and the MCP
  server entrypoint + `integrations/mcp-server/test_server.py`.
