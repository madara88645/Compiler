# Repo Hygiene Runbook

Prompt Compiler uses many short-lived agent branches. Clean them regularly so PR triage stays readable.

## Branch Audit

Run this from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/branch_audit.ps1 -IncludeDeleteCommands
```

The script reports:

- remote branches already merged into `origin/main`
- local merged branches that can be deleted directly
- local merged branches blocked by worktrees
- local branches whose upstream is gone
- remote branches not merged into `origin/main`
- stale worktree metadata that `git worktree prune` can remove

## Safe Cleanup Order

1. Confirm GitHub has no open PRs for the branches you plan to delete.
2. Delete only remote branches listed under merged remote branches.
3. Run `git fetch origin --prune`.
4. Run `git worktree prune -v` to remove stale metadata for missing worktrees.
5. Delete local merged branches that are not attached to worktrees.
6. Review worktree-blocked branches manually before deleting their worktree folders.

## Do Not Auto-Delete

- `main`
- branches with open PRs
- branches not merged into `origin/main`
- branches attached to a worktree with active uncommitted work
- scratch branches whose purpose is unclear until reviewed

## Scratch Files

Keep local PR triage exports, temporary diffs, coverage output, and browser automation state out of git. The root `.gitignore` covers common scratch files such as `pr*.txt`, `pr*.diff`, `prs*.json`, `.playwright-cli/`, `coverage.xml`, and `origin/`.
