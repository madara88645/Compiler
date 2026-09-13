# Main Compiler export evidence

Date: 2026-09-12

Offline/heuristics-only input: `Summarize alpha beta gamma in one sentence.`

The main compiler returned a one-step result and the `Download as Markdown` and `Download as JSON` actions both created files in the disposable QA Downloads check:

- `/Users/mehmetozel/Downloads/user-prompt.md` — contained the exact generated Goals/Tasks text.
- `/Users/mehmetozel/Downloads/compile-result.json` — parsed as valid JSON and contained the compile keys (`system_prompt`, `user_prompt`, `plan`, `ir`, `ir_v2`, `critique`, and `readiness_markdown`).

The JSON also contained five `ir_v2.metadata.context_suggestions` entries whose absolute paths pointed into the worktree's persisted/test RAG index, including `.tmp-test-run/.../inputs/alpha.txt` and `beta.txt`. This was observed after the prompt's `alpha`/`beta` terms matched indexed filenames. No file content was inserted. The finding is recorded as a P2 privacy/stale-library observation: sharing the JSON export can disclose local filesystem paths from prior indexed documents.
