# Agent Packs B3 (slice 1) — Render Dead IR Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the two dead `AgentExportIR` fields — `hook_suggestions` and `mcp_servers` — into real pack files for the `project-pack` and `pr-reviewer` pack types.

**Architecture:** Pure backend adapter work in `app/adapters/`. A new `mcp_servers.py` module holds a docs-verified registry and renders `.mcp.json`; `claude_code.py` gains two helpers that render an example hooks file, and both pack builders conditionally append the new files. `.claude/settings.json` is untouched.

**Tech Stack:** Python 3, Pydantic (`AgentExportIR`), pytest. Files are built as Python objects then `json.dumps`-ed; shell-safety via `shlex.quote`.

**Spec:** `docs/superpowers/specs/2026-07-04-agent-packs-b3-render-ir-fields-design.md`

**Branch:** `feat/agent-packs-render-ir-b3` (already created off `main`; the spec is committed on it).

---

## File Structure

**New files:**
- `app/adapters/mcp_servers.py` — `MCP_SERVER_REGISTRY`, `render_mcp_json`, `unregistered_servers`.
- `tests/test_mcp_servers.py` — unit tests for the registry/renderer.

**Modified files:**
- `app/adapters/claude_code.py` — add `import shlex`; add `_select_post_edit_suggestions` + `_hooks_example_json`; import from `mcp_servers`; append `.mcp.json` and `.claude/hooks.example.json` in `to_claude_project_pack` and `to_claude_pr_reviewer_pack`; append an unregistered-servers line in `_mcp_integration_notes`.
- `tests/test_export_adapters.py` — extend imports; add pack-level tests.

**Unchanged:** `claude_code.py :: _project_settings_json`, `app/adapters/agent_ir.py`, `app/adapters/agent_packs.py`, all web/API/MCP code.

**Command notes:** all commands run from repo root. Single file: `python -m pytest tests/test_mcp_servers.py -q`. Single test: `python -m pytest "tests/test_export_adapters.py::test_name" -q`. Known pre-existing flake unrelated to this work: `test_validate_summary_and_api_schemas` fails locally and on `main` (it hits 127.0.0.1:8000) — ignore it.

---

## Task 1: `mcp_servers.py` — registry, renderer, unregistered helper

**Files:**
- Create: `app/adapters/mcp_servers.py`
- Test: `tests/test_mcp_servers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_servers.py`:
```python
from __future__ import annotations

import json

from app.adapters.mcp_servers import (
    MCP_SERVER_REGISTRY,
    render_mcp_json,
    unregistered_servers,
)


def test_render_none_for_empty():
    assert render_mcp_json([]) is None


def test_render_none_for_unregistered_only():
    assert render_mcp_json(["figma", "jira"]) is None


def test_render_github_slack_secret_safe():
    payload = json.loads(render_mcp_json(["github", "slack"]))
    servers = payload["mcpServers"]
    assert servers["github"]["type"] == "http"
    assert servers["github"]["url"] == "https://api.githubcopilot.com/mcp/"
    assert servers["slack"]["url"] == "https://mcp.slack.com/mcp"
    # github's secret is an env placeholder, not a literal token
    assert servers["github"]["headers"]["Authorization"].startswith("Bearer ${")
    # slack (OAuth) carries no headers/env
    assert "headers" not in servers["slack"]
    assert "env" not in servers["slack"]
    # No literal secret anywhere: every headers/env value is a ${...} expansion
    for cfg in servers.values():
        for section in ("headers", "env"):
            for value in cfg.get(section, {}).values():
                assert "${" in value


def test_render_omits_unregistered():
    payload = json.loads(render_mcp_json(["github", "figma"]))
    assert "github" in payload["mcpServers"]
    assert "figma" not in payload["mcpServers"]


def test_registry_has_no_archived_npx_packages():
    # Guard against re-introducing the archived @modelcontextprotocol/server-* stubs.
    blob = json.dumps(MCP_SERVER_REGISTRY)
    assert "@modelcontextprotocol/server-" not in blob


def test_unregistered_servers():
    assert unregistered_servers(["github", "figma", "jira"]) == ["figma", "jira"]
    assert unregistered_servers(["github", "slack"]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp_servers.py -q`
Expected: FAIL — `ModuleNotFoundError: app.adapters.mcp_servers`.

- [ ] **Step 3: Write the implementation**

Create `app/adapters/mcp_servers.py`:
```python
"""Known MCP server config stubs for generated agent packs.

Configs verified 2026-07-04 against https://code.claude.com/docs/en/mcp.
The old @modelcontextprotocol/server-* npx packages are archived; the current
GitHub/Slack/Notion/Sentry servers are remote HTTP. `figma` and `jira` are
intentionally absent (no current config confirmed) and are surfaced in the
pack README instead. Secrets are only ${ENV} placeholders or OAuth (no secret).
"""

from __future__ import annotations

import json

MCP_SERVER_REGISTRY: dict[str, dict] = {
    "github": {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer ${GITHUB_PAT}"},
    },
    "slack": {"type": "http", "url": "https://mcp.slack.com/mcp"},
    "notion": {"type": "http", "url": "https://mcp.notion.com/mcp"},
    "sentry": {"type": "http", "url": "https://mcp.sentry.dev/mcp"},
}


def render_mcp_json(server_names: list[str]) -> str | None:
    """Render a .mcp.json for the registered servers among ``server_names``.

    Returns None when none of the names are registered. Registry order is used
    for deterministic output; unregistered names are ignored.
    """
    selected = {
        name: config
        for name, config in MCP_SERVER_REGISTRY.items()
        if name in server_names
    }
    if not selected:
        return None
    return json.dumps({"mcpServers": selected}, indent=2)


def unregistered_servers(server_names: list[str]) -> list[str]:
    """Detected server names that have no verified registry config."""
    return [name for name in server_names if name not in MCP_SERVER_REGISTRY]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_servers.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add app/adapters/mcp_servers.py tests/test_mcp_servers.py
git commit -m "feat(agent-packs): MCP server registry + .mcp.json renderer

Docs-verified current remote-HTTP configs for github/slack/notion/sentry;
figma/jira intentionally unregistered. Secrets are env placeholders or OAuth.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Emit `.mcp.json` from the pack builders + note unregistered servers

**Files:**
- Modify: `app/adapters/claude_code.py`
- Modify: `tests/test_export_adapters.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_export_adapters.py`, extend the `from app.adapters.claude_code import (...)` block to also import `to_claude_pr_reviewer_pack`:
```python
from app.adapters.claude_code import (
    to_agent_sdk_python,
    to_agent_sdk_typescript,
    to_claude_project_pack,
    to_claude_pr_reviewer_pack,
    to_claude_subagent,
    to_claude_mcp_tool_stub,
)
```
Then add these tests at the end of the file:
```python
def test_project_pack_emits_mcp_json_for_known_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github"])
    pack = to_claude_project_pack(ir)
    mcp_files = [f for f in pack if f["path"] == ".mcp.json"]
    assert len(mcp_files) == 1
    payload = json.loads(mcp_files[0]["content"])
    assert payload["mcpServers"]["github"]["url"] == "https://api.githubcopilot.com/mcp/"


def test_project_pack_no_mcp_json_when_no_servers():
    ir = AgentExportIR(name="X", mcp_servers=[])
    pack = to_claude_project_pack(ir)
    assert not any(f["path"] == ".mcp.json" for f in pack)


def test_pr_reviewer_pack_emits_mcp_json():
    ir = AgentExportIR(name="X", mcp_servers=["slack"])
    pack = to_claude_pr_reviewer_pack(ir)
    assert any(f["path"] == ".mcp.json" for f in pack)


def test_mcp_readme_notes_unregistered_servers():
    ir = AgentExportIR(name="X", mcp_servers=["github", "figma", "jira"])
    pack = to_claude_project_pack(ir)
    readme = next(f for f in pack if f["path"] == ".claude/mcp/README.md")
    assert "figma" in readme["content"]
    assert "jira" in readme["content"]


def test_mcp_readme_no_note_when_all_registered():
    ir = AgentExportIR(name="X", mcp_servers=["github"])
    pack = to_claude_project_pack(ir)
    readme = next(f for f in pack if f["path"] == ".claude/mcp/README.md")
    assert "not auto-configured" not in readme["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "tests/test_export_adapters.py::test_project_pack_emits_mcp_json_for_known_servers" "tests/test_export_adapters.py::test_mcp_readme_notes_unregistered_servers" -q`
Expected: FAIL — no `.mcp.json` file / README lacks the note (and possibly ImportError until the import line is added).

- [ ] **Step 3: Implement in `claude_code.py`**

(a) Add the import after the existing `from .agent_ir import AgentExportIR` line:
```python
from .mcp_servers import render_mcp_json, unregistered_servers
```

(b) Replace `to_claude_project_pack` with:
```python
def to_claude_project_pack(ir: AgentExportIR) -> list[dict[str, str]]:
    files = [
        {"path": "CLAUDE.md", "content": _project_claude_md(ir)},
        {"path": ".claude/settings.json", "content": _project_settings_json(ir)},
        to_claude_subagent(ir),
        {"path": ".github/workflows/claude.yml", "content": _github_action_workflow(ir)},
        {"path": ".claude/mcp/README.md", "content": _mcp_integration_notes(ir)},
    ]
    mcp_json = render_mcp_json(ir.mcp_servers)
    if mcp_json is not None:
        files.append({"path": ".mcp.json", "content": mcp_json})
    return files
```

(c) In `to_claude_pr_reviewer_pack`, insert the same append immediately before `return files`:
```python
    mcp_json = render_mcp_json(ir.mcp_servers)
    if mcp_json is not None:
        files.append({"path": ".mcp.json", "content": mcp_json})
    return files
```

(d) Replace `_mcp_integration_notes` with (keep the existing prose verbatim, add the trailing note):
```python
def _mcp_integration_notes(ir: AgentExportIR) -> str:
    notes = textwrap.dedent(
        f"""\
# MCP integration notes for {ir.name}

No MCP server configuration is generated because the request did not provide a verified command or server path.

Before adding an MCP server:

1. Identify an existing server entry point in the repository.
2. Run it locally and confirm its tool schema.
3. Add the verified command to the host client's MCP configuration.
4. Keep secrets in the host environment; do not write credentials into this pack.
"""
    )
    extra = unregistered_servers(ir.mcp_servers)
    if extra:
        notes += f"\nDetected but not auto-configured (add manually): {', '.join(extra)}.\n"
    return notes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_export_adapters.py -q`
Expected: PASS (new tests green; existing `test_claude_project_pack_output` etc. still green — additive).

- [ ] **Step 5: Commit**

```bash
git add app/adapters/claude_code.py tests/test_export_adapters.py
git commit -m "feat(agent-packs): emit .mcp.json from project-pack and pr-reviewer

Renders mcp_servers into a real .mcp.json for registered servers; unregistered
detected servers are noted in the MCP README instead of silently dropped.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Hooks-example helpers (`_select_post_edit_suggestions`, `_hooks_example_json`)

**Files:**
- Modify: `app/adapters/claude_code.py`
- Modify: `tests/test_export_adapters.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_export_adapters.py`:
```python
def test_select_post_edit_suggestions_exact():
    from app.adapters.claude_code import _select_post_edit_suggestions

    ir = AgentExportIR(
        name="X",
        hook_suggestions=[
            "Block reads of .env and secrets before tool execution.",
            "Run targeted tests or lint checks after code edits.",
            "Run frontend lint/build hooks after editing TSX or CSS.",
            "Require human confirmation before git push or deploy commands.",
        ],
    )
    assert _select_post_edit_suggestions(ir) == [
        "Run targeted tests or lint checks after code edits.",
        "Run frontend lint/build hooks after editing TSX or CSS.",
    ]


def test_hooks_example_none_without_post_edit():
    from app.adapters.claude_code import _hooks_example_json

    ir = AgentExportIR(
        name="X",
        hook_suggestions=[
            "Block reads of .env and secrets before tool execution.",
            "Require human confirmation before git push or deploy commands.",
        ],
    )
    assert _hooks_example_json(ir) is None


def test_hooks_example_shape_and_shell_safety():
    import subprocess

    from app.adapters.claude_code import _hooks_example_json

    tricky = "Run tests after code edits: it's `safe` $HOME \"ok\""
    ir = AgentExportIR(name="X", hook_suggestions=[tricky])
    content = _hooks_example_json(ir)
    data = json.loads(content)
    entry = data["hooks"]["PostToolUse"][0]
    assert entry["matcher"] == "Edit|Write"
    cmd = entry["hooks"][0]
    assert cmd["type"] == "command"
    assert cmd["command"].startswith("echo ")

    # The command is valid shell and echoes the literal text (no $HOME/backtick expansion).
    result = subprocess.run(cmd["command"], shell=True, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == tricky
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "tests/test_export_adapters.py::test_select_post_edit_suggestions_exact" -q`
Expected: FAIL — `ImportError: cannot import name '_select_post_edit_suggestions'`.

- [ ] **Step 3: Implement in `claude_code.py`**

(a) Add `import shlex` to the imports block (after `import re`):
```python
import json
import re
import shlex
import textwrap
```

(b) Add the two helpers (place them just above `_project_settings_json`):
```python
def _select_post_edit_suggestions(ir: AgentExportIR) -> list[str]:
    """Hook suggestions that describe a post-edit action (test/lint/frontend build)."""
    return [
        s
        for s in ir.hook_suggestions
        if "after" in s.lower() and ("edit" in s.lower() or "code" in s.lower())
    ]


def _hooks_example_json(ir: AgentExportIR) -> str | None:
    """Render an example Claude Code hooks file from post-edit suggestions.

    Returns None when there is nothing to render. This is an *example* file the
    user adopts; it is never read live by Claude Code, so it does not nag on edits.
    The suggestion text is passed through shlex.quote so the echo command is valid
    shell for any content (no injection/expansion).
    """
    selected = _select_post_edit_suggestions(ir)
    if not selected:
        return None
    post_tool_use = [
        {
            "matcher": "Edit|Write",
            "hooks": [{"type": "command", "command": f"echo {shlex.quote(s)}"}],
        }
        for s in selected
    ]
    data = {
        "//": (
            'Example Claude Code hooks. Copy the "hooks" block into '
            ".claude/settings.json and replace each echo with your real command."
        ),
        "hooks": {"PostToolUse": post_tool_use},
    }
    return json.dumps(data, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest "tests/test_export_adapters.py::test_select_post_edit_suggestions_exact" "tests/test_export_adapters.py::test_hooks_example_none_without_post_edit" "tests/test_export_adapters.py::test_hooks_example_shape_and_shell_safety" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/adapters/claude_code.py tests/test_export_adapters.py
git commit -m "feat(agent-packs): render hook_suggestions into an example hooks scaffold

Adds _select_post_edit_suggestions + _hooks_example_json: post-edit suggestions
become a shell-safe (shlex.quote) example hooks JSON, no live per-edit hook.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Emit `.claude/hooks.example.json` from the pack builders

**Files:**
- Modify: `app/adapters/claude_code.py`
- Modify: `tests/test_export_adapters.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_export_adapters.py`, extend the claude_code import block to also import `to_claude_subagent_bundle`:
```python
from app.adapters.claude_code import (
    to_agent_sdk_python,
    to_agent_sdk_typescript,
    to_claude_project_pack,
    to_claude_pr_reviewer_pack,
    to_claude_subagent,
    to_claude_subagent_bundle,
    to_claude_mcp_tool_stub,
)
```
Add these tests:
```python
def test_project_pack_emits_hooks_example():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    pack = to_claude_project_pack(ir)
    hooks_files = [f for f in pack if f["path"] == ".claude/hooks.example.json"]
    assert len(hooks_files) == 1
    data = json.loads(hooks_files[0]["content"])
    assert data["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"
    assert data["hooks"]["PostToolUse"][0]["hooks"][0]["command"].startswith("echo ")
    # settings.json is unchanged (no hooks key)
    settings = next(f for f in pack if f["path"] == ".claude/settings.json")
    assert "hooks" not in json.loads(settings["content"])


def test_pr_reviewer_pack_emits_hooks_example():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    pack = to_claude_pr_reviewer_pack(ir)
    assert any(f["path"] == ".claude/hooks.example.json" for f in pack)


def test_subagent_bundle_has_no_hooks_or_mcp_or_settings():
    ir = parse_agent_markdown(SINGLE_AGENT_MARKDOWN)
    bundle = to_claude_subagent_bundle(ir)
    paths = {f["path"] for f in bundle}
    assert ".mcp.json" not in paths
    assert ".claude/hooks.example.json" not in paths
    assert ".claude/settings.json" not in paths
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "tests/test_export_adapters.py::test_project_pack_emits_hooks_example" -q`
Expected: FAIL — no `.claude/hooks.example.json` in the pack.

- [ ] **Step 3: Implement in `claude_code.py`**

In `to_claude_project_pack`, add the hooks append after the `.mcp.json` append (before `return files`):
```python
    mcp_json = render_mcp_json(ir.mcp_servers)
    if mcp_json is not None:
        files.append({"path": ".mcp.json", "content": mcp_json})
    hooks_example = _hooks_example_json(ir)
    if hooks_example is not None:
        files.append({"path": ".claude/hooks.example.json", "content": hooks_example})
    return files
```
Add the identical two hooks lines in `to_claude_pr_reviewer_pack`, right after its `.mcp.json` append and before `return files`:
```python
    hooks_example = _hooks_example_json(ir)
    if hooks_example is not None:
        files.append({"path": ".claude/hooks.example.json", "content": hooks_example})
    return files
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_export_adapters.py -q`
Expected: PASS (all new + existing tests green).

- [ ] **Step 5: Commit**

```bash
git add app/adapters/claude_code.py tests/test_export_adapters.py
git commit -m "feat(agent-packs): emit .claude/hooks.example.json from packs

project-pack and pr-reviewer now ship an example hooks scaffold; settings.json
stays unchanged and subagent/mcp-stub packs are unaffected.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Full verification gate

**Files:** none (verification only).

- [ ] **Step 1: Focused export + MCP suites**

Run: `python -m pytest tests/test_export_adapters.py tests/test_mcp_servers.py -q`
Expected: PASS.

- [ ] **Step 2: Full backend suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, except the known pre-existing flake `test_validate_summary_and_api_schemas` (hits 127.0.0.1:8000, also fails on `main`). If that is the only failure, the gate passes.

- [ ] **Step 3: Stop for review — do NOT open a PR automatically**

Per project rules, never push/PR/merge without Mehmet's explicit approval. Report: changed files, out-of-scope changes (none — backend adapter only), test results, and the boundary note (no `.env`/auth/LLM/deploy/secrets touched; `.mcp.json` uses env placeholders / OAuth only). Then ask whether to open the PR.

---

## Self-Review

**1. Spec coverage:**
- `hook_suggestions` → `.claude/hooks.example.json` → Task 3 (helpers) + Task 4 (wiring). ✅
- Selection rule (deterministic, exact-string tested, substring semantics) → Task 3 tests. ✅
- Shell-safety via `shlex.quote` (quotes/`$`/backtick test) → Task 3. ✅
- `settings.json` unchanged (no live hooks) → asserted in Task 4. ✅
- `mcp_servers` → `.mcp.json` with docs-verified current configs → Task 1 + Task 2. ✅
- Secret invariant (env placeholder / OAuth, no literal secret; no archived npx) → Task 1 tests. ✅
- Unregistered figma/jira → README note (reachable, tested) → Task 2. ✅
- project-pack + pr-reviewer only; subagent/mcp-stub unaffected → Task 4 test. ✅
- Existing project-pack assertions still pass (additive) → Task 2 Step 4 / Task 4 Step 4. ✅
- Gate (`pytest tests/`) → Task 5. ✅

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N" — every code step shows complete code. ✅

**3. Type/name consistency:**
- `render_mcp_json`, `unregistered_servers`, `MCP_SERVER_REGISTRY` (Task 1) used identically in Task 2. ✅
- `_select_post_edit_suggestions`, `_hooks_example_json` (Task 3) used in Task 4. ✅
- Import block grows monotonically: `to_claude_pr_reviewer_pack` (Task 2), `to_claude_subagent_bundle` (Task 4) — final block matches every symbol used. ✅
- `.mcp.json` and `.claude/hooks.example.json` path strings identical across builder edits and tests. ✅
