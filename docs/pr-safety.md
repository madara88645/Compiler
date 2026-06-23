# PR Safety — Merge Readiness Layer (v0)

AI PR review bots leave comments. **PR Safety** answers the human's question instead:
**should I merge this PR, hold it, split it, or rebase it?**

It looks at a pull request's **scope, changed files, risky areas, test coverage and branch
freshness** and returns a single deterministic verdict plus the signals behind it.

> **v0 is an offline, heuristic advisory.** It runs entirely on pasted input — no GitHub
> API, no AI calls, no auth. It **never blocks a merge**; it gives a human a fast read on
> merge readiness. Treat it as advice, not a gate.

---

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **merge** | No blocking safety signals detected — proceed with normal review. |
| **hold** | Risky area, missing tests, or scope mismatch — address before merging. |
| **split** | Too large / spans too many areas — break into smaller, focused PRs. |
| **rebase** | Branch is stale (far behind base) — update before merging. |

The verdict is picked deterministically: a stale branch → `rebase`; an oversized/multi-area
change → `split`; a risky-area / missing-test / scope-mismatch signal → `hold`; otherwise
`merge`.

---

## Use it in the browser

1. Open **`/pr-safety`** (the **PR Safety** item in the sidebar).
2. Paste the PR's **title**, **description**, and **changed files** (one path per line).
3. Optionally enter **commits behind** (how far the branch trails its base).
4. Click **Analyze PR**.
5. Read the verdict, risky areas, test-coverage and scope signals, branch freshness, and
   recommendations.
6. Use **Copy as Markdown** / **Download .md** to drop a GitHub-ready summary into the PR
   description or a review note. (Copy/paste is intentional — PR Safety never comments for you.)

No sign-in, no setup, nothing leaves your machine beyond the single analysis request.

---

## Use it from the API

The browser page is a thin client over one endpoint: `POST /pr-safety/report`.

```bash
curl -s -X POST http://127.0.0.1:8080/pr-safety/report \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add password reset endpoint",
    "description": "Adds POST /auth/reset to issue and consume reset tokens.",
    "changed_files": [
      "app/auth/reset.py",
      "app/auth/tokens.py",
      "api/routes/auth.py"
    ],
    "commits_behind": 3
  }'
```

Request fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | string | yes | PR title. |
| `description` | string | yes | PR body / description. |
| `changed_files` | string[] | yes | One path per entry; at least one. |
| `commits_behind` | integer ≥ 0 | no | Omit if unknown — branch freshness reports `unknown`. |

The response contains `verdict`, `changed_files` (grouped), `risky_areas`, `test_coverage`,
`branch_freshness`, `scope_match`, and `recommendations`.

---

## Worked examples

### 1. Docs-only PR → `merge`

A documentation change touches no source files and no risky areas.

```json
{
  "title": "Update README setup section",
  "description": "docs: clarify local setup steps and fix broken links",
  "changed_files": ["README.md", "docs/setup.md", "docs/troubleshooting.md"]
}
```

**Verdict: `merge`** — *"No blocking safety signals detected; proceed with normal review"*
and *"Docs-only change; lightweight review should be sufficient."*

### 2. Auth change without tests → `hold`

Authentication code changes with no matching test file is the classic "look twice" case.

```json
{
  "title": "Add login endpoint",
  "description": "Adds POST /auth/login with session handling and token issuance",
  "changed_files": ["app/auth/login.py", "app/auth/session.py", "api/routes/auth.py"]
}
```

**Verdict: `hold`** — risky areas flagged (`auth`, `api`), test-coverage status `gap`
(each source file changed without a matching test), recommendation to add test coverage
before merging.

### 3. Stale branch → `rebase`

A branch far behind its base risks silent conflicts — see the real-world regression that
motivated this layer (a stale "small" PR that quietly reverted behavior).

```json
{
  "title": "Tweak logging helper",
  "description": "Small logging change",
  "changed_files": ["app/logging.py"],
  "commits_behind": 12
}
```

**Verdict: `rebase`** — branch freshness `stale` (≥ 10 commits behind),
*"Rebase onto the latest base branch before merging."* (Rebase takes precedence over other
signals.)

### 4. Large, multi-directory PR → `split`

A change that spans many top-level areas is hard to review safely.

```json
{
  "title": "Tidy logging helper",
  "description": "Small logging tweak that ended up touching many areas across the repo",
  "changed_files": [
    "app/logging.py", "app/utils.py", "api/routes/health.py",
    "web/app/page.tsx", "web/app/layout.tsx", "docs/logging.md",
    "tests/test_logging.py", "scripts/build.sh", "config/settings.yaml",
    "integrations/mcp/server.py"
  ]
}
```

**Verdict: `split`** — *"Split this PR into smaller, focused changesets"* (plus test-gap
notes for the changed source files).

---

## Sharing PR Safety

- **Send the link.** Point a reviewer or teammate at `/pr-safety` — no account needed.
- **Paste the verdict.** Use **Copy as Markdown** and drop the report into the PR
  description or a review comment so the merge decision is recorded next to the PR.
- **Scriptable.** The `curl` call above runs in any shell or CI step. An advisory
  GitHub Action sketch (surfacing the report as a CI summary, never as a merge gate) is
  tracked on the **Product Readiness: PR Safety Layer** milestone.

---

## What v0 is not

- Not a merge gate or a required status check.
- Not connected to GitHub — it reads only what you paste.
- Not an AI reviewer — the verdict is deterministic heuristics, so the same input always
  gives the same answer.

Repo-aware fetching, access tiers, and a CI integration are tracked as separate follow-ups
on the **Product Readiness: PR Safety Layer** milestone.
