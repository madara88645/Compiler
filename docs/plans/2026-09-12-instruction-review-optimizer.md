# Instruction review and optimizer modernization

## Product decision

Keep the existing compiler, optimizer, benchmark and repository checks. Agentic Coding becomes one collapsible sidebar section containing Projects, Agent Generator and Skill Generator. Existing URLs remain usable. Instruction review is an action inside Projects, including a standalone entry for people who already have instruction files and do not need a saved project brief.

The intended user is a vibe coder maintaining a growing repository. They can paste or upload existing instructions, inspect repeated rules and possible conflicts, compare an original with a suggested version, then explicitly choose which version to take back to their repository. This release supplies a concrete maintenance tool without requiring a full product rewrite.

## Instruction review

- Text-only deterministic backend analysis at `POST /instruction-review/analyze`; frontend at `/agentic-coding/instructions`.
- Up to 12 relative-name files and 120,000 combined characters. Environment settings may lower those limits. No server-side filesystem collection, repository modification or provider call.
- Cleanup is limited to adjacent exact plain rules in the same scope. Different sections, conditions, code, checklists, numbered lists and rules with child content remain available for manual review.
- Literal command contradictions are potential conflicts, not semantic verdicts. Relative links are only checked against an explicitly supplied repository file list; absent inventory means unverified.
- Moving rules into imported files is not presented as automatic context savings.
- Inputs remain unchanged. Changing an input clears the prior report and all accepted suggestions. Downloads default to the original; using a suggested version requires an explicit per-file selection.
- Nested file paths are retained inside ZIP downloads. A visible destination identifies where the file belongs.

## Optimizer and model estimates

Use the official [OpenRouter Models API](https://openrouter.ai/api/v1/models) and its [schema documentation](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties) for exact model identifiers, tokenizer labels, context limits and published input/output rates. Store the verification date with the reviewed snapshot. Keep legacy identifiers compatible while adding current options.

Prompt token counts are estimates: a tokenizer-family label is not proof that a local encoding exactly reproduces the provider's accounting. Distinguish estimates for a future prompt from tokens reported by an actual optimizer call. Missing prices or provider usage must remain visibly unavailable. A selected estimate model must not be represented as the configured optimizer model when they differ.

Protected prompt material must survive optimization. If an output drops required placeholders, paths, URLs or code, keep the original and explain the rejected rewrite. These guards do not establish full semantic equivalence or better model performance.

## Acceptance checks

- Collapsing Agentic Coding removes its child links from navigation and keyboard traversal; old and new routes select the appropriate item.
- Review suggestions preserve scope and literal content; adversarial repeated rules cannot expand conflict references quadratically.
- File edits invalidate results; failure retains input; original/accepted exports contain the selected content and preserve nested destinations.
- Model metadata matches the dated official snapshot; unknown prices do not look like free calls.
- Run focused backend regressions and existing API smoke gates, full frontend tests/contracts, lint and build. Exercise the actual local frontend proxy against the running backend.

## Limits

This is an incremental maintenance release. It does not automatically split or synchronize instruction files, run agents, prove instruction adherence, or establish user adoption. Simulated persona review is design feedback; live provider output remains a separate check from mocked regression tests.

## Completed validation (12 September 2026)

- 117 backend API smoke, instruction review and compiler regression tests passed; 145 optimizer, token estimate and cost tests passed.
- Full frontend suite: 366 tests passed. Frontend contracts: 61 passed. Model catalog Node tests: 3 passed. ESLint, Ruff and production Next.js build passed.
- Live keyless frontend proxy review returned HTTP 200, preserved both checkbox states and original text, suggested an adjacent duplicate removal and found a missing reference against the supplied file inventory.
- One real OpenRouter optimizer request through the frontend proxy succeeded on the configured GPT-OSS 20B. Estimated prompt tokens changed from 32 to 27 while retaining a placeholder and file path. The provider reported 582 input and 256 output tokens, with a reported USD 0.000052718 charge, separate from the catalog-based USD 0.00005074 estimate. This single smoke run does not establish optimization quality generally.
- A live local-mode request made no cloud call and reported an unmet token budget for a long multilingual input. Local browser compression preserves literals and only removes redundant prose spacing; it warns instead of truncating content to hit a target.
- Browser checks covered the collapsible section, actual instruction review results, clearing stale results after input edits, and local optimizer output. The instruction page had no horizontal document overflow at 390px.
- ZIP contents and nested paths passed regression tests. The in-app browser's download-event wait timed out, so receiving the exported file through that browser was not independently confirmed. Clipboard content was also not independently confirmed through its clipboard API; successful copy feedback alone is not treated as content verification.
- Independent Luna/max persona review accepted Instruction Review as a usable first-pass maintenance tool after checkbox, scope, conflict-output bounds and path preservation fixes. Optimizer review found budget visibility, provider validation and legacy pricing issues; all were corrected and covered by focused regressions.
- Changes are local to the isolated worktree. No deployment or remote push was performed.
