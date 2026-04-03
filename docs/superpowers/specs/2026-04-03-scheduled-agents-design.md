# Scheduled Morning Agents — Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Author:** Claude (brainstorming session)

---

## Overview

Three autonomous Claude Code agents run each morning via scheduled task. Each agent independently reads the codebase, identifies the highest-value improvement within its domain, implements it, and opens a PR. The owner reviews and extends the PR as needed.

---

## Shared Protocol (all 3 agents)

Every agent follows the same 4-phase decision framework:

### Phase 1 — Read Context
```bash
git log --oneline -20          # what was recently done?
gh pr list --state open        # what PRs are already in flight?
```
Then scan the files specific to its domain.

### Phase 2 — Scan for Opportunities
Priority order:
1. `TODO` / `FIXME` / `HACK` comments
2. Untested public functions (no corresponding test)
3. Performance bottlenecks (uncompiled regex, redundant computation, O(n²) loops)
4. Code quality issues (duplicate logic, oversized functions, missing error handling)
5. Small feature opportunities (hinted at in comments or adjacent code)

### Phase 3 — Select & Implement
- Pick the highest-value work not covered by recent commits or open PRs
- Create a branch: `agent/<agent-name>/YYYY-MM-DD`
- Implement the change and run the relevant tests

### Phase 4 — Open PR
- **Title:** concise summary of what changed
- **Body:** why this was selected, what changed, how it was tested
- **Label:** `agent-generated`

### Forbidden Zones (all agents)
These files must never be modified:
- `api/auth.py`
- `fly.toml`
- DB migration files
- `schema/`

---

## Agent 1 — General Development

**Purpose:** Broad codebase improvements — quality, tests, performance, refactoring.

**Scan targets:**
```
app/              → compiler.py, heuristics, plugins, rag, adapters
api/routes/       → endpoint logic
cli/commands/     → CLI implementations
tests/            → coverage gaps
web/              → hooks, components (small JS/TS fixes)
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

**Scan targets:**
```
app/heuristics/              → linter.py, security.py, __init__.py
app/heuristics/handlers/     → safety.py, policy.py, risk.py, domain_expert.py
app/llm_engine/prompts/      → LLM system prompts
docs/promptc-safe-workflows.md
.jules/sentinel.md           → past security learnings
tests/                       → heuristics/safety test coverage
```

**Decision criterion:**
> "Which change measurably improves the project's safety or intent-detection quality today?"

**Example PRs:**
- Add new jailbreak/injection patterns to `linter.py` with tests
- Write edge-case test for overlapping risk domains (e.g. health + finance combined)
- Complete a missing `restricted` data sensitivity branch in `policy.py`
- Write regression tests for vulnerabilities recorded in `sentinel.md`
- Fix a handler that should emit `DiagnosticItem`s in IRv2 but doesn't

---

## Agent 3 — Extension

**Purpose:** Improve the Chrome extension and MCP server — reliability, UX, new integrations.

**Scan targets:**
```
extension/                   → manifest.json, content.js, background.js, popup.js, config.mjs
integrations/mcp-server/     → server.py (FastMCP)
web/                         → API integration points shared with extension
api/routes/                  → endpoints called by the extension
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

- Each agent runs on its own cron schedule (suggested: staggered by 15 min to avoid git conflicts)
- Branch naming: `agent/general/YYYY-MM-DD`, `agent/safety/YYYY-MM-DD`, `agent/extension/YYYY-MM-DD`
- If no meaningful opportunity is found, the agent exits without opening a PR
- Agents do not communicate with each other — conflict avoidance is handled by Phase 1 (reading open PRs)
