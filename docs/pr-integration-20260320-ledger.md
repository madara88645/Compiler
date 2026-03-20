# PR Integration Ledger - 2026-03-20

Branch: `codex/pr-integration-20260320`

Purpose: track open PR intake, integration order, verification, and keep/drop decisions before anything is considered for `main`.

## Intake Snapshot

| PR | Title | Mergeable | Check Status | Risk | Current Verdict |
| --- | --- | --- | --- | --- | --- |
| #200 | Fix path traversal and username leak in default db paths | MERGEABLE | green | high | keep candidate |
| #201 | Add error handling test for compile_fast endpoint | MERGEABLE | green | low | merge in wave 1 |
| #202 | optimize heuristic multiple-substring matching in hot loops | MERGEABLE | green | medium | merge in wave 1 |
| #203 | Add visual feedback to Copy to Clipboard buttons | MERGEABLE | green but empty diff | suspicious | hold |
| #204 | Optimize aggregation loops | MERGEABLE | green | medium but noisy | hold / extract subset only |
| #205 | Optimize vector dot product calculation | CONFLICTING | partial green | medium | patch/re-resolve |
| #206 | Fix path traversal in /rag/upload | MERGEABLE | lint failed | high | patch/re-resolve |
| #207 | Fix XSS vulnerability in DiffViewer | CONFLICTING | partial green | high | patch/re-resolve |
| #208 | Optimize regex pattern matching in psycholinguist | MERGEABLE | green | medium | merge in wave 1 |
| #209 | Add authentication to missing API endpoints | CONFLICTING | partial green | critical | patch/re-resolve |

## Baseline

- Clean isolated worktree created from `origin/main`
- Targeted baseline suite passed:
  - `tests/test_auth_fast_path.py`
  - `tests/heuristics/test_psycholinguist.py`
  - `tests/test_rag_upload.py`
  - `tests/test_history_integration.py`
  - `tests/test_rag_history_store.py`

## Execution Log

- [ ] Wave 1: `#201`
- [ ] Wave 1: `#202`
- [ ] Wave 1: `#208`
- [ ] Wave 2: `#200`
- [ ] Hold review: `#203`
- [ ] Hold review: `#204`
- [ ] Wave 4: `#209`
- [ ] Wave 4: `#206`
- [ ] Wave 4: `#205`
- [ ] Wave 5: `#207`

## Notes

- `#203` currently appears to have no file diff through GitHub API and should not be merged unless that changes.
- `#204` includes unrelated deletions of root-level diagnostic files and should not be merged wholesale.
- `#209` changes public API auth behavior and needs explicit review at the end even if tests pass.
