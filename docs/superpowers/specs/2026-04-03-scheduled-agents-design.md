# Scheduled Morning Agents — Design Spec

**Date:** 2026-04-03
**Status:** Approved — authoritative implementation reference
**Author:** Claude Code (brainstorming session, owner-approved)

---

## Prerequisites (one-time setup)

Before the first agent run, complete the following:

1. **Create the PR label:**
   ```bash
   gh label create agent-generated --color 0075ca --description "Opened by a scheduled Claude Code agent"
   ```
2. **Verify `gh` CLI is authenticated** (`gh auth status`) with write access to the repo.
3. **Confirm the scheduling mechanism** is configured (cron, GitHub Actions, or Task Scheduler — implementation plan will specify).

---

## Overview

Three autonomous Claude Code agents run each morning via scheduled task. Each agent independently reads the codebase, identifies the highest-value improvement within its domain, implements it, and opens a PR. The owner reviews and extends the PR as needed.

---

## Shared Protocol (all 3 agents)

Every agent follows the same 4-phase decision framework:

### Phase 1 — Read Context
```bash
git log --oneline -20                        # what was recently done?
gh pr list --state open --base main          # what PRs are already in flight?
# For each open PR number N, get its changed files:
gh pr view <N> --json files --jq '.files[].path'
```
Build a "blocked files" set from all open PR file lists. If any file you intend to modify is in this set, skip it and look for another opportunity.

### Phase 2 — Scan for Opportunities
Priority order:
1. `TODO` / `FIXME` / `HACK` comments
2. Untested public functions (no corresponding test)
3. Performance bottlenecks (uncompiled regex, redundant computation, O(n²) loops)
4. Code quality issues (duplicate logic, oversized functions, missing error handling)
5. Small feature opportunities (hinted at in comments or adjacent code)

### Phase 3 — Select & Implement
- Pick the highest-value work not covered by recent commits or open PRs
- Agent names for branch naming: `general`, `safety`, `extension`
- Create a branch: `agent/general/YYYY-MM-DD`, `agent/safety/YYYY-MM-DD`, or `agent/extension/YYYY-MM-DD`
- If the branch already exists (retry on same day): delete it and recreate (`git branch -D <branch> && git checkout -b <branch>`) only if no commits exist on it yet; otherwise append `-v2`, `-v3`, etc.
- Implement the change
- Run `pytest tests/` (or the scoped path for the changed module) and confirm zero failures before proceeding. If the test suite cannot be run, note this explicitly in the PR body.
- **No-op rule:** If every candidate change has no behavioral impact (i.e. it only affects formatting, comments, or whitespace), exit without opening a PR. Line count alone is not a criterion — a 3-line error handler fix qualifies; a 200-line reformat does not.

### Phase 4 — Open PR
- **Base branch:** `main`
- **Title:** concise summary of what changed
- **Body:** why this was selected, what changed, how it was tested
- **Label:** `agent-generated` (must pre-exist in the repo; create once with `gh label create agent-generated --color 0075ca`)

### Forbidden Zones (all agents)
These files must never be modified:
- `api/auth.py`
- `fly.toml`
- DB migration files
- `schema/`

---

## File Ownership (conflict avoidance)

To prevent duplicate PRs when scan zones overlap, each file path has exactly one owning agent:

| Path | Owner |
|------|-------|
| `tests/` (excluding `tests/heuristics/`, `tests/security/`) | Agent 1 — General |
| `tests/heuristics/` | Agent 2 — Safety |
| `tests/security/` | Agent 2 — Safety |
| `web/` — scan-time rule: grep the file for any string literal matching a path value in `extension/config.mjs`; if found, skip it (Agent 3 owned); otherwise Agent 1 may modify it | Agent 1 — General (with yield) |
| `web/` files containing a string literal path from `extension/config.mjs` | Agent 3 — Extension |
| `api/routes/` — scan-time rule: grep `extension/config.mjs` for the route's path string; if found there, skip it (Agent 3 owned); otherwise Agent 1 may modify it | Agent 1 — General (with yield) |
| `api/routes/` files whose path string appears as a literal in `extension/config.mjs` | Agent 3 — Extension |
| `app/heuristics/` | Agent 2 — Safety |
| `app/llm_engine/prompts/` | Agent 2 — Safety |
| `docs/promptc-safe-workflows.md` | Agent 2 — Safety |
| `.jules/sentinel.md` | Agent 2 — Safety |
| `.jules/palette.md` | Agent 3 — Extension |
| `extension/` | Agent 3 — Extension |
| `integrations/` | Agent 3 — Extension |
| Everything else under `app/`, `cli/` | Agent 1 — General |

When in doubt, Agent 1 yields to Agents 2 and 3 for their respective specialist files.

---

## Agent 1 — General Development

**Purpose:** Broad codebase improvements — quality, tests, performance, refactoring.

**Scan targets (owned files only — see ownership table above):**
```
app/compiler.py, app/plugins.py, app/rag/, app/adapters/, app/agents/
api/routes/        → general endpoint logic (non-extension routes)
cli/commands/      → CLI implementations
tests/             → coverage gaps (excluding tests/heuristics/, tests/security/)
web/               → hooks, components (non-extension JS/TS)
```

**Decision criterion:**
> "Which single change most concretely advances the project today?"

**Example PRs:**
- Extract duplicate domain detection logic across handlers into a shared utility
- Add missing unit tests for `HybridCompiler`
- Refactor an oversized CLI command into smaller focused functions
- Optimize O(n) embedding search in `app/rag/simple_index.py`

---

## Agent 2 — Safety & Intent

**Purpose:** Evolve the safety layer — prompt injection defense, intent detection, policy workflows.

**Scan targets (owned files only — see ownership table above):**
```
app/heuristics/              → linter.py, security.py, __init__.py
app/heuristics/handlers/     → safety.py, policy.py, risk.py, domain_expert.py
app/llm_engine/prompts/      → LLM system prompts
docs/promptc-safe-workflows.md
.jules/sentinel.md           → past security learnings
tests/heuristics/            → heuristics test coverage
tests/security/              → security test coverage
```

**Decision criterion:**
> "Which change measurably improves the project's safety or intent-detection quality today?"

**Agent 2 no-op addendum:** Any new heuristic pattern added to `linter.py` or `security.py` must be accompanied by at least one test. A pattern addition with no test does not qualify as a meaningful change and triggers the no-op rule.

**Example PRs:**
- Add new jailbreak/injection patterns to `linter.py` with tests
- Write edge-case test for overlapping risk domains (e.g. health + finance combined)
- Complete a missing `restricted` data sensitivity branch in `policy.py`
- Write regression tests for vulnerabilities recorded in `sentinel.md`
- Fix a handler that should emit `DiagnosticItem`s in IRv2 but doesn't

---

## Agent 3 — Extension

**Purpose:** Improve the Chrome extension and MCP server — reliability, UX, new integrations.

**Scan targets (owned files only — see ownership table above):**
```
extension/                   → manifest.json, content.js, background.js, popup.js, config.mjs
integrations/mcp-server/     → server.py (FastMCP)
web/                         → only files that import extension/ or call extension-specific routes
api/routes/                  → only routes referenced in extension/config.mjs
.jules/palette.md            → past UX learnings
```

**Decision criterion:**
> "Which change makes the extension or MCP integration more reliable or more capable today?"

**Example PRs:**
- Add support for a new chat interface (e.g. Grok, Copilot) in `content.js`
- Show meaningful error feedback in popup when API call fails
- Expose `compile_v2` as a tool in the MCP server
- Catch unhandled promise rejections in the service worker
- Replace hardcoded API endpoint in `config.mjs` with a user-configurable setting

---

## Implementation Notes

- Each agent runs on its own cron schedule. Suggested times (UTC): Agent 1 at 06:00, Agent 2 at 06:15, Agent 3 at 06:30. Staggering prevents two agents from branching off `main` simultaneously.
- If two agents accidentally produce PRs that conflict at merge time, resolve by hand — this spec does not automate merge conflict resolution.
- If no meaningful opportunity is found (see no-op rule in Phase 3), the agent exits without opening a PR.
- Agents do not communicate with each other — conflict avoidance relies on the ownership table and Phase 1 open PR check.
- **Pre-requisite:** create the `agent-generated` label once before first run: `gh label create agent-generated --color 0075ca --description "Opened by a scheduled Claude Code agent"`
