# Agent Packs B3 (slice 1) — Render Dead IR Fields (Design)

- **Date:** 2026-07-04
- **Status:** Approved (design), pending spec review
- **Branch:** `feat/agent-packs-render-ir-b3` (off `main`, independent of B1 / PR #933)
- **Surface:** `app/adapters/**` only — backend adapter. No web, API-route, or MCP changes.

## Problem

`AgentExportIR` (in `app/adapters/agent_ir.py`) infers two fields that no pack renders
into a file:

- `hook_suggestions` — natural-language hook ideas. `_infer_hook_suggestions` always emits
  two base items ("Block reads of .env and secrets before tool execution.", "Run targeted
  tests or lint checks after code edits.") and, by keyword, up to two more ("Run frontend
  lint/build hooks after editing TSX or CSS.", "Require human confirmation before git push
  or deploy commands.").
- `mcp_servers` — recognized server names from a fixed mapping in `_infer_mcp_servers`:
  `github`, `figma`, `slack`, `notion`, `jira`, `sentry` (only these six are ever emitted).

Both are computed and dropped: `_project_settings_json(ir)` emits only a `permissions`
block, and the only MCP artifact is a prose `.claude/mcp/README.md` — no real `.mcp.json`.

This is the first of four independent B3 slices (CLAUDE.md smart-merge, CLI vehicle,
GitHub-PR vehicle are separate specs). This slice renders the two dead fields into files.

## Goals / Non-goals

**Goals:** render `hook_suggestions` and `mcp_servers` into real, honest artifacts for the
pack types that carry `.claude/settings.json` — **project-pack** and **pr-reviewer** — with
no fake commands, no fake secrets, and no per-edit nag.

**Non-goals:** subagent and mcp-tool-stub packs (verified below: neither emits
`.claude/settings.json`); a **live** `hooks` block in `.claude/settings.json` (deferred to
the B1 follow-up, which supplies the real `detected_commands`); repo-aware real commands;
CLAUDE.md smart-merge; CLI / GitHub-PR vehicles; any web, API-route, or MCP-server change
(the web file tree already renders any file in `manifest.files`).

## Approved decisions

- **Approach A — safe-real + honest.** Emit real, valid files; never a guessed command,
  stale package, or literal secret.
- **Hooks render as an example file, not live settings** (user decision). Because slice 1
  has no real test/lint command, a live `PostToolUse` hook would fire on every edit and
  only print a reminder — the "prompt-pretty, not executable" anti-pattern the project
  ethos forbids. Instead we emit a clearly-labeled `.claude/hooks.example.json` scaffold the
  user adopts. `.claude/settings.json` is **unchanged** in this slice.
- **`.mcp.json` uses current, verified configs** — the old `@modelcontextprotocol/server-*`
  npx packages are archived; the current GitHub/Slack/Notion/Sentry servers are remote HTTP.
- **Independent of B1** — branch off `main`.
- Honors CLAUDE.md: "executable, not just prompt-pretty" **and** "avoid hallucinated
  requirements and fake APIs" **and** "never expose secrets".

## Design

All changes are in `app/adapters/`. `agent_ir.py` and `agent_packs.py` are unchanged.

### 1. `hook_suggestions` → `.claude/hooks.example.json`

New helper in `claude_code.py`:

- **Selection** — `_select_post_edit_suggestions(ir) -> list[str]`: from `ir.hook_suggestions`,
  keep each `s` where `"after" in s.lower() and ("edit" in s.lower() or "code" in s.lower())`
  (two complete membership tests). Applied to the current fixed suggestion set this selects
  exactly:
  - "Run targeted tests or lint checks after code edits." (`after` + `code`)
  - "Run frontend lint/build hooks after editing TSX or CSS." (`after` + `edit` as a
    **substring** of "editing" — keep substring semantics, do not switch to word boundaries)

  and excludes the `.env`-block and push/deploy suggestions — not because of any
  cross-check against `permissions` (there is none) but because they are not post-edit
  (no `after`). This slice's classifier is asserted against these exact strings in tests;
  it is coupled to the current fixed set owned by `_infer_hook_suggestions`.
- **Rendering** — `_hooks_example_json(ir) -> str | None`: returns `None` when the selection
  is empty; otherwise a JSON string of the form below, built as a Python dict then
  `json.dumps(..., indent=2)` (never string concatenation):
  ```json
  {
    "//": "Example Claude Code hooks. Copy the \"hooks\" block into .claude/settings.json and replace each echo with your real command.",
    "hooks": {
      "PostToolUse": [
        { "matcher": "Edit|Write", "hooks": [ { "type": "command", "command": "echo 'Run targeted tests or lint checks after code edits.'" } ] },
        { "matcher": "Edit|Write", "hooks": [ { "type": "command", "command": "echo 'Run frontend lint/build hooks after editing TSX or CSS.'" } ] }
      ]
    }
  }
  ```
  - One `PostToolUse` entry per selected suggestion; the suggestion text is the echo
    payload (so the field is actually rendered and visible).
  - **Shell safety:** the echo argument is produced with `shlex.quote(suggestion)`, so the
    command is valid shell for **any** suggestion content (quotes, `$`, backticks) — not a
    hand-rolled quote-strip. A test feeds a suggestion containing `'`, `"`, `$`, and a
    backtick and asserts the emitted command parses (`bash -n`) and echoes the literal.
  - It is an **example** file: Claude Code never reads `.claude/hooks.example.json`, so it
    does not nag on edits. If a user copies the `hooks` block into `settings.json`, the
    echoes are harmless and the `"//"` note tells them to replace each with a real command.
- **Schema (verified 2026-07-04 against code.claude.com/docs/en/hooks):** hooks config is
  `hooks.<Event>[].{matcher, hooks: [{type: "command", command}]}`; the `matcher` is an
  **exact-string, pipe/comma-separated list** (so `"Edit|Write"` matches the `Edit` and
  `Write` tools — it is not a regex, hence no escaping concerns). This shape is normative
  for the example; verification only confirmed field names.
- **Wiring:** `to_claude_project_pack` and `to_claude_pr_reviewer_pack` append
  `{"path": ".claude/hooks.example.json", "content": ...}` only when `_hooks_example_json`
  returns non-None. `.claude/hooks.example.json` classifies as kind `"files"` via the
  existing `_classify_kind` (it is not CLAUDE.md/settings.json/agents/mcp/workflow/README),
  is in `_preview_order()`, and is rendered by the web tree with no client change. In
  practice it is always emitted for these two pack types (the base "tests/lint after code
  edits" suggestion is always present).

### 2. `mcp_servers` → `.mcp.json`

New module `app/adapters/mcp_servers.py`:

- `MCP_SERVER_REGISTRY: dict[str, dict]` — pinned to the servers whose **current** config is
  verified (2026-07-04) against code.claude.com/docs/en/mcp. All four are remote HTTP:
  ```python
  {
    "github":  {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": "Bearer ${GITHUB_PAT}"}},
    "slack":   {"type": "http", "url": "https://mcp.slack.com/mcp"},
    "notion":  {"type": "http", "url": "https://mcp.notion.com/mcp"},
    "sentry":  {"type": "http", "url": "https://mcp.sentry.dev/mcp"},
  }
  ```
  `figma` and `jira` are **deliberately not registered** — the Claude Code docs do not
  confirm a current config for them, so shipping a guessed one would violate the ethos.
- `render_mcp_json(server_names) -> str | None` — returns a pretty-printed
  `{"mcpServers": {…}}` for the names present in the registry (preserving a stable order),
  or `None` when none are registered. Names not in the registry are **not** written.
- `unregistered_servers(server_names) -> list[str]` — the detected names absent from the
  registry (e.g. `["figma", "jira"]`), used for the README note (below).
- **Secret invariant:** no value under `headers`/`env` is ever a literal secret; any
  credential is a `${VAR}` expansion (e.g. GitHub's `Bearer ${GITHUB_PAT}`). OAuth servers
  (slack/notion/sentry) carry **no** `env`/`headers` at all — authentication is `/mcp`
  OAuth. Env expansion (`${VAR}` / `${VAR:-default}`) is supported in `.mcp.json`
  command/args/env/url/headers.
- **Wiring:** `to_claude_project_pack` and `to_claude_pr_reviewer_pack` append
  `{"path": ".mcp.json", "content": render_mcp_json(ir.mcp_servers)}` only when it returns
  non-None. `.mcp.json` classifies as kind `"mcp"` via `_classify_kind` (`"mcp" in
  normalized.lower()`) — confirmed it does not hit an earlier branch (it is not `CLAUDE.md`,
  does not end with `settings.json`, is not under `/agents/`). `"mcp"` is in
  `_preview_order()`; the web tree renders it.

### 3. `.claude/mcp/README.md` — note unregistered detected servers

`_mcp_integration_notes(ir)` appends one short line when `unregistered_servers(ir.mcp_servers)`
is non-empty, e.g. "Detected but not auto-configured (add manually): figma, jira." This keeps
`figma`/`jira` from being silently dropped. Required (not optional) and tested.

## File-level impact

**New:**
- `app/adapters/mcp_servers.py` — registry, `render_mcp_json`, `unregistered_servers`.
- Tests (in `tests/test_export_adapters.py`, plus a focused `tests/test_mcp_servers.py` for
  the pure registry/renderer).

**Changed:**
- `app/adapters/claude_code.py` — add `_select_post_edit_suggestions` and
  `_hooks_example_json`; `to_claude_project_pack` and `to_claude_pr_reviewer_pack`
  conditionally append `.claude/hooks.example.json` and `.mcp.json`; `_mcp_integration_notes`
  appends the unregistered-servers line.

**Unchanged (intentionally):**
- `app/adapters/claude_code.py :: _project_settings_json` — `.claude/settings.json` is not
  touched this slice (no live `hooks`).
- `app/adapters/agent_ir.py`, `app/adapters/agent_packs.py`.
- All web, API-route, and MCP-server code.

## Testing

Add to `tests/test_export_adapters.py` / `tests/test_mcp_servers.py` (pure, deterministic,
no network):

- **hooks example present:** `to_claude_project_pack(ir)` (default IR → base suggestions
  present) yields a `.claude/hooks.example.json` whose JSON parses, has
  `hooks.PostToolUse[0].matcher == "Edit|Write"` and `hooks.PostToolUse[0].hooks[0]` ==
  `{"type": "command", "command": <starts with "echo ">}`; and the settings.json in the same
  pack has **no** `hooks` key (unchanged).
- **selection exactness:** `_select_post_edit_suggestions` over the real base+frontend+deploy
  suggestion set returns exactly the two post-edit strings; over the env/push-only subset
  returns `[]` and `_hooks_example_json` returns `None`.
- **shell safety:** `_hooks_example_json` for a suggestion containing `'`, `"`, `$`, and a
  backtick produces a `command` that `bash -n` accepts and that echoes the literal (no
  expansion).
- **pr-reviewer parity:** `to_claude_pr_reviewer_pack` emits the same
  `.claude/hooks.example.json` behavior.
- **.mcp.json present + secret-safe:** `render_mcp_json(["github", "slack"])` parses, has
  `mcpServers.github.type == "http"` and `...url == "https://api.githubcopilot.com/mcp/"`,
  `mcpServers.slack.url == "https://mcp.slack.com/mcp"`, github's
  `headers.Authorization` contains `${` (an env expansion, **not** a literal token), and
  slack has no `env`/`headers`. Assert no value anywhere matches a literal-secret shape
  (every value that appears under `headers`/`env` starts with `${`).
- **.mcp.json omits unregistered + None:** `render_mcp_json(["figma"])` is `None`;
  `render_mcp_json([])` is `None`; `render_mcp_json(["github", "figma"])` contains `github`
  and not `figma`.
- **README note:** an IR with `mcp_servers` including `figma`/`jira` yields
  `.claude/mcp/README.md` mentioning `figma` and `jira`; an IR with only registered servers
  does not add the note.
- **unaffected packs:** `to_claude_subagent_bundle` and `to_claude_mcp_tool_stub` emit no
  `.mcp.json` and no `.claude/hooks.example.json` (verified by construction: neither builder
  lists `.claude/settings.json` or these files).
- Existing assertions (`test_claude_project_pack_output`,
  `test_export_api_endpoint_claude_project_pack`) still pass — changes are additive (they
  only assert `.claude/settings.json` is present).

**Gate before PR:** `python -m pytest tests/test_export_adapters.py -q`, then
`python -m pytest tests/test_export_adapters.py tests/test_mcp_servers.py -q`, then
`python -m pytest tests/ -q`.

## Risks & mitigations

- **Stale MCP configs.** Registry pinned to docs-verified current configs (2026-07-04);
  unverified servers (figma/jira) are documented, not fake-configured. A dated comment in
  `mcp_servers.py` records the verification source for future re-checks.
- **Invalid JSON / shell injection.** Both files are built as Python objects then
  `json.dumps`; the only free text reaching a shell is passed through `shlex.quote`.
- **Coupling to a fixed suggestion set.** Selection correctness is asserted against the exact
  current strings; if `_infer_hook_suggestions` changes, the tests catch drift.

## Out of scope / follow-ups

- Live `hooks` in `.claude/settings.json` using B1's real `detected_commands` (needs B1).
- `figma` / `jira` registry entries once a current config is confirmed.
- Other B3 slices: CLAUDE.md smart-merge; CLI vehicle; GitHub-PR vehicle.
- Hooks/`.mcp.json` for subagent / mcp-tool-stub packs.
