# PR Safety — GitHub Action advisory sketch

This is a **sketch** for running [PR Safety](pr-safety.md) inside CI as an **advisory
artifact**. It is a future-facing exploration (#834 on the *Product Readiness: PR Safety
Layer* milestone), not an active part of this repo's CI.

Example workflow: [`examples/github/pr-safety-advisory.yml`](../examples/github/pr-safety-advisory.yml).
It lives under `examples/` on purpose so it does **not** run here — copy it to
`.github/workflows/` in your own project to try it.

## Design principles (v0)

- **Advisory only.** It posts the report to the GitHub **job summary**; it never blocks a
  merge and never fails the build on a `hold` / `split` / `rebase` verdict
  (`continue-on-error: true`).
- **No merge gate.** It is not a required status check. Do not add it to branch protection.
- **No secrets.** No GitHub App, no OAuth, no provider keys. `permissions: contents: read`.
- **Offline.** It runs the in-repo deterministic analyzer (`app.pr_safety.analyzer`) on the
  PR's own metadata; nothing leaves the runner.

## How the sketch works

On every `pull_request` event the job:

1. Checks out the repo with full history (`fetch-depth: 0`).
2. Derives the **changed files** from `git diff --name-only base...head`.
3. Derives **commits behind** from `git rev-list --count head..base` (branch-freshness signal).
4. Calls `analyze_pr_safety(title, body, changed_files, commits_behind=...)`.
5. Writes a short Markdown summary (verdict + recommendations) to `$GITHUB_STEP_SUMMARY`.

The reviewer then sees a verdict (`merge` / `hold` / `split` / `rebase`) and recommendations
right in the PR's Checks tab — a fast read on merge readiness, alongside (not instead of)
human review.

## Explicitly out of scope for v0

- ❌ Merge blocking / required checks / branch-protection changes.
- ❌ Auto-commenting on the PR, GitHub App, or OAuth installation flow.
- ❌ Secrets or provider credentials.
- ❌ Repo-aware fetching beyond the PR's own diff (tracked separately as #833).

## Possible later iterations (not now)

- Render the full Markdown report (the same one the `/pr-safety` UI exports) instead of the
  compact summary.
- Optionally post the summary as a sticky PR comment (write permission, still advisory).
- Offer it as a reusable composite action.

These belong to later, opt-in tiers and are intentionally left as ideas here.
