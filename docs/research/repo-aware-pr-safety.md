# Repo-aware PR Safety — research notes

**Issue:** [#833](https://github.com/madara88645/Compiler/issues/833)
**Status:** Research only — no implementation in this doc.
**Date:** 2026-07-08

## Current state (v0)

PR Safety today is **diff-only and offline**. The analyzer (`app/pr_safety/analyzer.py`) takes four inputs — title, description, changed file paths, optional `commits_behind` — and runs deterministic path heuristics (`path_rules.py`): risky-area globs, test-file name matching, scope-term extraction, size/split thresholds.

| Surface | How inputs arrive | Uses `git_context.py`? |
|---------|-------------------|--------------------------|
| Web `/pr-safety` | User pastes title, body, file list | No |
| API `POST /pr-safety/report` | Same JSON body as web | No |
| CLI `promptc pr-safety` | Manual args, stdin, or `--from-git` | Yes (`--from-git` only) |
| GitHub Action sketch (`examples/github/pr-safety-advisory.yml`) | `git diff` + PR event metadata in CI | Inline git, not the module |

`git_context.py` shells out to local git (`diff --name-only`, `rev-list`, `log`) with no network and no GitHub API. It is tested but **not wired to the API or web UI**.

**Gap:** the product sees a flat list of paths. It does not know who owns those paths, which CI jobs exercise them, what test command the repo actually runs, or whether GitHub checks are green.

## What "repo-aware" could mean

Repo-aware PR Safety would enrich the same offline verdict with **repository facts**, not replace human review.

| Signal | Diff-only (today) | Repo-aware (candidate) |
|--------|-------------------|------------------------|
| Changed files | Path list from user/git diff | Same, plus optional line-count / rename hints |
| Risky areas | Glob on path (`*auth*`, `.env`) | + map to CODEOWNERS / security team |
| Test coverage | Filename pairing in the PR (`test_foo.py`) | + repo's real test command (`pytest`, `npm test`) and whether CI workflow paths overlap changed dirs |
| Branch freshness | Optional `commits_behind` integer | Same; could add "base branch protection rules" later |
| Scope match | Title/description terms vs paths | + stack detection (`pyproject.toml`, `package.json`) via existing `app/repo_inspect/` |
| CI / checks | Not considered | Read workflow YAML paths; optionally surface check conclusions (needs GitHub API) |

The guiding constraint from product rules: **public web flows must not ask visitors for GitHub tokens or Prompt Compiler API keys.** Repo-aware tiers that need credentials belong in CI, CLI, or an installed GitHub App — not in a paste-your-PAT text box.

## Integration options

### Option A — Local filesystem enrichment (CLI + Action)

**Idea:** When the tool runs inside a checkout (`--from-git` or the advisory Action), read a small, fixed set of repo files and attach a `repo_signals` section to the report.

**Examples of reads (no API):**
- `.github/CODEOWNERS` → suggested reviewers per changed path
- `.github/workflows/*.yml` → which jobs likely cover changed top-level dirs
- `app/repo_inspect/` → detected `test` / `lint` commands from `package.json`, `Makefile`, `pyproject.toml`

| | |
|---|---|
| **Effort** | **S–M** (1–2 weeks): parsers + report fields + Action/CLI wiring |
| **Needs** | Local clone on dev machine or CI runner. No new scopes, no secrets. |
| **Risks** | Heuristic false positives (CODEOWNERS globs, workflow `paths:` filters are messy). Must stay advisory. |

### Option B — GitHub API PR import (server or CI)

**Idea:** Given `owner/repo#123` or a PR URL, fetch title, body, file list, and `commits_behind` from the GitHub REST API instead of manual paste.

| | |
|---|---|
| **Effort** | **M** for a CI-only script using `GITHUB_TOKEN` (`permissions: pull-requests: read`). **L** for a multi-tenant web "paste PR URL" flow (GitHub App install, token storage, abuse controls). |
| **Needs** | `pull_requests: read` (+ `contents: read` if fetching blobs). In Actions, the ephemeral `GITHUB_TOKEN` is enough. For the public web, a **GitHub App** installed per org/repo — not a user PAT in the browser. |
| **Risks** | Rate limits (5k/hr per installation), token storage on Fly, SSRF on URL input, scope creep into "we need write access to comment." Conflicts with the no-browser-secrets rule unless App-based. |

### Option C — GitHub App with PR comments + check awareness

**Idea:** Install a Compiler GitHub App that posts an advisory comment, reads check-run status, and nudges reviewers when auth files change without a green test job.

| | |
|---|---|
| **Effort** | **L** (4+ weeks): App registration, webhook handler, comment dedup, org onboarding UX. |
| **Needs** | App with `pull_requests: write`, `checks: read`, webhook endpoint, persistent installation store. |
| **Risks** | Feels like a merge gate even if labeled advisory; comment noise; permission friction for enterprises; operational burden (webhooks, retries, GitHub abuse reports). |

## Recommendation

**Ship Option A first.** It delivers the highest user value per effort, reuses code already in the repo (`git_context.py`, `repo_inspect/`), needs no credentials, and fits every surface that already has filesystem access (CLI, CI). It directly answers "what should I know about *this* repo?" without becoming a GitHub product.

**Defer Option B's web tier** until there is a GitHub App story; a PAT-paste field is the wrong UX and the wrong security model for Prompt Compiler.

**Treat Option C as a later paid/advanced tier** only after the advisory Action proves adoption.

### Suggested first implementation PR (after this research)

Scope a single vertical slice — not the full matrix above:

1. Add `app/pr_safety/repo_signals.py` (read-only parsers for CODEOWNERS + workflow path filters).
2. Extend `analyze_pr_safety(..., repo_root: Path | None)` with an optional `repo_signals` block on `PrSafetyReport` (owners, overlapping workflows, detected test command).
3. Wire it only through `cli/commands/pr_safety.py --from-git` and update `examples/github/pr-safety-advisory.yml` to print the new section.
4. Tests with fixture files under `tests/fixtures/pr_safety_repo/`.
5. **Do not** change the web form or public API request shape yet.

That PR is reviewable, offline, and backward-compatible.

## Explicit non-goals (for now)

Do **not** build yet:

- Browser fields for GitHub PATs, OAuth popups, or "connect your repo" on the public `/pr-safety` page.
- Merge blocking, required status checks, or branch-protection integration.
- Auto-posting PR comments without an explicit, separately installed GitHub App.
- LLM-generated diff review or "AI says merge" — PR Safety stays deterministic heuristics.
- Full import/dependency graph analysis (needs AST indexing; separate product surface).
- Cloning arbitrary user repos onto the Fly API host.
- Storing long-lived GitHub tokens in Prompt Compiler's server `.env` for multi-tenant use.

## References in this repo

- Analyzer & models: `app/pr_safety/`
- Local git helpers: `app/pr_safety/git_context.py`
- API route (manual input only): `api/routes/pr_safety.py`
- CLI `--from-git`: `cli/commands/pr_safety.py`
- Action sketch: `examples/github/pr-safety-advisory.yml`, `docs/pr-safety-github-action.md`
- Reusable stack/command detection: `app/repo_inspect/`
- Prior repo-aware pattern (Agent Packs): `docs/superpowers/specs/2026-07-03-agent-packs-mcp-repo-aware-design.md`
