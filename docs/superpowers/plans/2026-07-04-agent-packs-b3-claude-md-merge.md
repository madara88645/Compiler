# Agent Packs B3 (slice 2) — CLAUDE.md Smart Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a repo already has a `CLAUDE.md`, non-destructively merge the generated guidance into it (append only the `##` sections the user lacks) and apply that merge in place instead of writing `CLAUDE.md.new`.

**Architecture:** A pure `merge_claude_md` in `app/repo_inspect/`; the backend `repo-plan` handler calls it for the `CLAUDE.md` path and returns a `"merge"` plan action with the merged content in the manifest; the MCP `apply_agent_pack` treats `"merge"` paths as overwrite-able so the merge lands in place. B1's `write_pack_files` is unchanged.

**Tech Stack:** Python 3, FastAPI (repo-plan), pytest. Pure functions built with `re` + `str`; the MCP client uses `httpx` (mocked in tests).

**Spec:** `docs/superpowers/specs/2026-07-04-agent-packs-b3-claude-md-merge-design.md`

**Branch:** `feat/agent-packs-claude-md-merge` (already created off `main`; spec committed on it).

---

## File Structure

**New:**
- `app/repo_inspect/claude_md_merge.py` — `MARKER`, `merge_claude_md`.
- `tests/test_claude_md_merge.py` — pure-function tests.

**Modified:**
- `api/routes/agent_packs.py` — CLAUDE.md merge special-case in `repo_plan_claude_agent_pack`.
- `integrations/mcp-server/server.py` — `apply_agent_pack` merge-path auto-overwrite.
- `tests/test_agent_packs_repo_plan.py` — update the existing `"overwrite"` assertion to `"merge"`; add identical/create cases.
- `integrations/mcp-server/test_server.py` — apply-merge-in-place test.

**Unchanged:** `integrations/mcp-server/repo_write.py`, `app/adapters/**`, `app/repo_inspect/models.py`/`detect.py`, all web/download code.

**Command notes:** run from repo root. Single file: `python -m pytest tests/test_claude_md_merge.py -q`. Format changed Python before pushing: `uvx ruff@0.1.14 format <files>` (the CI "Smoke" check is pre-commit ruff v0.1.14). Known pre-existing flake unrelated to this work: `test_validate_summary_and_api_schemas` (hits 127.0.0.1:8000; also fails on `main`).

---

## Task 1: `merge_claude_md` — the pure section-aware merge

**Files:**
- Create: `app/repo_inspect/claude_md_merge.py`
- Test: `tests/test_claude_md_merge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_md_merge.py`:
```python
from app.repo_inspect.claude_md_merge import MARKER, merge_claude_md


def test_preserve_prefix_and_append_new():
    existing = "# My Guide\n\n## Setup\nrun make\n"
    generated = "# Gen\n\n## Setup\nother setup\n\n## Deploy\nship it\n"
    merged = merge_claude_md(existing, generated)
    # existing content is preserved verbatim as the prefix (up to the marker)
    assert merged.startswith(existing.rstrip())
    assert merged.split("\n\n" + MARKER, 1)[0] == existing.rstrip()
    # only the section the user lacks is appended
    assert "## Deploy\nship it" in merged
    # the generated "Setup" body is NOT appended (heading already present)
    assert "other setup" not in merged


def test_no_new_sections_returns_existing_unchanged():
    existing = "# G\n\n## Setup\na\n\n## Deploy\nb\n"
    generated = "# Gen\n\n## setup\nx\n\n## DEPLOY\ny\n"  # same keys, different case
    assert merge_claude_md(existing, generated) == existing


def test_idempotent():
    existing = "# G\n\n## Setup\na\n"
    generated = "# Gen\n\n## Setup\na\n\n## Deploy\nb\n"
    once = merge_claude_md(existing, generated)
    assert merge_claude_md(once, generated) == once


def test_same_heading_different_body_is_dropped():
    # Accepted limitation: same heading key -> generated section not merged.
    existing = "## Security\nshort\n"
    generated = "## Security\nlong detailed policy\n"
    assert merge_claude_md(existing, generated) == existing


def test_duplicate_key_within_generated_appended_once():
    existing = "# Title only\n"
    generated = "## Setup\na\n\n## setup\nb\n"
    merged = merge_claude_md(existing, generated)
    assert merged.count("<!--") == 1
    assert merged.count("## Setup") + merged.count("## setup") == 1


def test_existing_without_sections_appends_all():
    existing = "# Just a title\n"
    generated = "## A\nx\n\n## B\ny\n"
    merged = merge_claude_md(existing, generated)
    assert "## A\nx" in merged
    assert "## B\ny" in merged


def test_generated_without_sections_returns_existing():
    existing = "# G\n\n## Setup\na\n"
    generated = "# Gen\n\nsome intro prose only\n"
    assert merge_claude_md(existing, generated) == existing


def test_heading_without_space_is_not_a_heading():
    existing = "# G\n"
    generated = "##NotAHeading\nbody\n\n## Real\nkeep\n"
    merged = merge_claude_md(existing, generated)
    # only "## Real" is a section; "##NotAHeading" is body of nothing (before first heading)
    assert "## Real\nkeep" in merged
    assert "##NotAHeading" not in merged


def test_fence_in_generated_not_a_heading():
    existing = "# G\n"
    generated = "## Code\n```\n## inside fence\n```\nafter\n\n## Real\nkeep\n"
    merged = merge_claude_md(existing, generated)
    # "## inside fence" stays inside the Code section body, not a separate section
    assert "## inside fence" in merged
    assert merged.count("<!--") == 1  # single marker
    # both real sections appended
    assert "## Code" in merged and "## Real" in merged


def test_fence_in_existing_does_not_shadow_generated_heading():
    existing = "# G\n\n```\n## Deploy\nfake\n```\n"
    generated = "## Deploy\nreal deploy steps\n"
    merged = merge_claude_md(existing, generated)
    # the fenced "## Deploy" in existing is NOT a real heading, so generated Deploy IS added
    assert "real deploy steps" in merged


def test_mixed_fence_delimiters():
    existing = "# G\n"
    generated = "## A\nx\n\n~~~\n```\n## Y\n~~~\n\n## B\nz\n"
    merged = merge_claude_md(existing, generated)
    # "## Y" is inside the ~~~ block (which is not closed by ```), so not a section
    assert "## A" in merged and "## B" in merged
    assert "## Y" in merged  # present, but as body of section A, not its own section


def test_crlf_existing_preserved():
    existing = "# Guide\r\n\r\n## Setup\r\nrun\r\n"
    generated = "## Deploy\nship\n"
    merged = merge_claude_md(existing, generated)
    assert merged.startswith("# Guide\r\n")
    assert "\r\n## Setup\r\nrun" in merged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_md_merge.py -q`
Expected: FAIL — `ModuleNotFoundError: app.repo_inspect.claude_md_merge`.

- [ ] **Step 3: Write the implementation**

Create `app/repo_inspect/claude_md_merge.py`:
```python
"""Section-aware, append-new-only merge of a generated CLAUDE.md into an existing one.

The user's existing content is preserved verbatim; only generated level-2 (``## ``)
sections whose heading the user lacks are appended, under a marker comment. Idempotent for
a fixed ``generated`` input. See the design spec for the full contract.
"""

from __future__ import annotations

import re

MARKER = "<!-- Added by Prompt Compiler: sections not already in your CLAUDE.md -->"

_HEADING_RE = re.compile(r"^##[ \t]+(.+?)\s*$")  # level-2 only; "##Foo" (no space) is not a heading
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")         # >=3 backticks or tildes after leading whitespace


def _heading_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _iter_sections(md: str) -> list[tuple[str, str]]:
    """(heading_key, section_text) for each level-2 section, fence-aware."""
    fence: tuple[str, int] | None = None
    out: list[tuple[str, str]] = []
    key: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        fence_m = _FENCE_RE.match(line.lstrip())
        if fence_m:
            run = fence_m.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif fence[0] == run[0] and len(run) >= fence[1]:
                fence = None
            if key is not None:
                buf.append(line)
            continue
        heading = None if fence is not None else _HEADING_RE.match(line)
        if heading:
            if key is not None:
                out.append((key, "\n".join(buf)))
            key = _heading_key(heading.group(1))
            buf = [line]
        elif key is not None:
            buf.append(line)
    if key is not None:
        out.append((key, "\n".join(buf)))
    return out


def merge_claude_md(existing: str, generated: str) -> str:
    """Append generated ``##`` sections the user lacks; preserve existing verbatim."""
    seen = {k for k, _ in _iter_sections(existing)}
    new_sections: list[str] = []
    for key, text in _iter_sections(generated):
        if key in seen:
            continue
        seen.add(key)
        new_sections.append(text.rstrip())
    if not new_sections:
        return existing
    return existing.rstrip() + "\n\n" + MARKER + "\n\n" + "\n\n".join(new_sections) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_claude_md_merge.py -q`
Expected: PASS (12 tests).

- [ ] **Step 5: Format + commit**

```bash
uvx ruff@0.1.14 format app/repo_inspect/claude_md_merge.py tests/test_claude_md_merge.py
git add app/repo_inspect/claude_md_merge.py tests/test_claude_md_merge.py
git commit -m "feat(agent-packs): section-aware CLAUDE.md merge helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Wire the merge into the `repo-plan` handler

**Files:**
- Modify: `api/routes/agent_packs.py`
- Modify: `tests/test_agent_packs_repo_plan.py`

- [ ] **Step 1: Update the existing test + add cases**

In `tests/test_agent_packs_repo_plan.py`, change the existing assertion in
`test_repo_plan_returns_manifest_and_diffs` from:
```python
    # CLAUDE.md already exists -> flagged as an overwrite in the plan
    claude = next(p for p in data["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "overwrite"
```
to:
```python
    # CLAUDE.md already exists -> merged (existing "# existing guide" has no ## sections,
    # so every generated ## section is appended)
    claude = next(p for p in data["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "merge"
    claude_file = next(f for f in data["manifest"]["files"] if f["path"] == "CLAUDE.md")
    assert claude_file["content"].startswith("# existing guide")
    assert "Added by Prompt Compiler" in claude_file["content"]
```
Then add two tests at the end of the file:
```python
def test_repo_plan_claude_md_identical_when_all_sections_present():
    # An existing CLAUDE.md that already contains every generated ## heading -> "identical"
    # (merge finds no new section, so merged == existing). The generated project-pack
    # CLAUDE.md emits exactly these level-2 headings (see _project_claude_md).
    existing_claude = (
        "# My Guide\n\n## Project context\n\n## Objectives\n\n## Constraints\n\n"
        "## Workflow\n\n## Declared technology context\n\n## Validation contract\n\n"
        "## Claude Code configuration\n"
    )
    body = {
        "pack_type": "project-pack",
        "goal": "g",
        "repo_facts": {"files": {"CLAUDE.md": existing_claude}, "tree": ["CLAUDE.md"]},
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    claude = next(p for p in r.json()["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "identical"


def test_repo_plan_claude_md_create_when_absent():
    body = {
        "pack_type": "project-pack",
        "goal": "g",
        "repo_facts": {"files": {"package.json": "{}"}, "tree": ["package.json"]},
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    claude = next(p for p in r.json()["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "create"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_agent_packs_repo_plan.py -q`
Expected: FAIL — `test_repo_plan_returns_manifest_and_diffs` (still "overwrite") and the new merge/create-action assertions.

- [ ] **Step 3: Implement in `api/routes/agent_packs.py`**

(a) Add the import next to the existing repo_inspect import:
```python
from app.repo_inspect import RepoFacts, derive_repo_context
from app.repo_inspect.claude_md_merge import merge_claude_md
```

(b) Replace the plan-building + return block (the current `existing = req.repo_facts.files` / `plan = [...]` / `return {...}`) with:
```python
    existing = req.repo_facts.files
    data = manifest.model_dump()
    plan: list[dict] = []
    for f in data["files"]:
        path, content = f["path"], f["content"]
        if path == "CLAUDE.md" and "CLAUDE.md" in existing:
            merged = merge_claude_md(existing["CLAUDE.md"], content)
            f["content"] = merged
            plan.append(
                {
                    "path": path,
                    "action": "identical" if merged == existing["CLAUDE.md"] else "merge",
                }
            )
        else:
            plan.append({"path": path, "action": _diff_action(existing, path, content)})
    return {
        "manifest": data,
        "plan": plan,
        "detected": {
            "stack": ctx.stack_summary(),
            "commands": ctx.command_map(),
            "has_existing_claude_md": ctx.has_existing_claude_md,
        },
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_agent_packs_repo_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Format + commit**

```bash
uvx ruff@0.1.14 format api/routes/agent_packs.py tests/test_agent_packs_repo_plan.py
git add api/routes/agent_packs.py tests/test_agent_packs_repo_plan.py
git commit -m "feat(agent-packs): repo-plan merges an existing CLAUDE.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Apply the merge in place (`apply_agent_pack`)

**Files:**
- Modify: `integrations/mcp-server/server.py`
- Modify: `integrations/mcp-server/test_server.py`

- [ ] **Step 1: Write the failing tests**

Add to `integrations/mcp-server/test_server.py`:
```python
def test_apply_agent_pack_merges_claude_md_in_place(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "CLAUDE.md").write_text("# Existing\n\n## Setup\nrun make\n")
    merged = "# Existing\n\n## Setup\nrun make\n\n<!-- marker -->\n\n## Deploy\nship\n"
    manifest = {"files": [{"path": "CLAUDE.md", "content": merged}]}
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse({"manifest": manifest, "plan": [{"path": "CLAUDE.md", "action": "merge"}]})
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.apply_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    assert (tmp_path / "CLAUDE.md").read_text() == merged  # written in place
    assert not (tmp_path / "CLAUDE.md.new").exists()       # not a .new conflict
    assert result["written"]["overwritten"] == ["CLAUDE.md"]


def test_apply_agent_pack_non_merge_conflict_still_new(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "README.md").write_text("old")
    manifest = {"files": [{"path": "README.md", "content": "new"}]}
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse({"manifest": manifest, "plan": [{"path": "README.md", "action": "overwrite"}]})
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        asyncio.run(server.apply_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    # An "overwrite"-action file the caller did NOT confirm still lands as .new (no-clobber).
    assert (tmp_path / "README.md").read_text() == "old"
    assert (tmp_path / "README.md.new").read_text() == "new"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd integrations/mcp-server && python -m pytest test_server.py -q -k "merges_claude_md_in_place"`
Expected: FAIL — the merged CLAUDE.md is currently written as `CLAUDE.md.new` (merge path not yet auto-overwritten), so the in-place assertion fails.

- [ ] **Step 3: Implement in `integrations/mcp-server/server.py`**

Replace the body of `apply_agent_pack` (the `result = await _post_json(...)` through `return ...`) with:
```python
    facts = collect_repo_facts(path)
    result = await _post_json(
        "/agent-packs/claude/repo-plan",
        {"pack_type": pack_type, "goal": goal, "risk_mode": risk_mode, "repo_facts": facts},
    )
    merge_paths = [p["path"] for p in result["plan"] if p.get("action") == "merge"]
    effective_overwrite = list(dict.fromkeys((overwrite or []) + merge_paths))
    written = write_pack_files(path, result["manifest"]["files"], effective_overwrite)
    return {"written": written, "plan": result["plan"]}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd integrations/mcp-server && python -m pytest test_server.py -q`
Expected: PASS (existing tests + the two new ones).

- [ ] **Step 5: Format + commit**

```bash
uvx ruff@0.1.14 format integrations/mcp-server/server.py integrations/mcp-server/test_server.py
git add integrations/mcp-server/server.py integrations/mcp-server/test_server.py
git commit -m "feat(agent-packs): apply CLAUDE.md merge in place, not as .new

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Full verification gate

**Files:** none.

- [ ] **Step 1: Focused suites**

Run: `python -m pytest tests/test_claude_md_merge.py tests/test_agent_packs_repo_plan.py -q` then `cd integrations/mcp-server && python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Full backend suite**

Run: `python -m pytest tests/ -q`
Expected: PASS except the known pre-existing flake `test_validate_summary_and_api_schemas` (127.0.0.1:8000; also fails on `main`). If that is the only failure, the gate passes.

- [ ] **Step 3: Format check (Smoke parity)**

Run: `uvx ruff@0.1.14 format --check app/repo_inspect/claude_md_merge.py api/routes/agent_packs.py integrations/mcp-server/server.py tests/test_claude_md_merge.py tests/test_agent_packs_repo_plan.py integrations/mcp-server/test_server.py`
Expected: "already formatted" for all changed files.

- [ ] **Step 4: Stop for review — do NOT open a PR automatically**

Per project rules, never push/PR/merge without Mehmet's explicit approval. Report: changed files, out-of-scope changes (none), test results, and the boundary note (only `CLAUDE.md` merged, non-destructively; no `.env`/auth/deploy/secret touched). Then ask whether to open the PR.

---

## Self-Review

**1. Spec coverage:**
- Pure section-aware append-new merge (fence-aware both sides, idempotent, dedup, edge cases) → Task 1 (impl + 12 tests). ✅
- Accepted limitation (same-key drop) as a conscious contract → Task 1 `test_same_heading_different_body_is_dropped`. ✅
- CRLF / preserve-prefix invariants → Task 1 `test_crlf_existing_preserved`, `test_preserve_prefix_and_append_new`. ✅
- repo-plan "merge"/"identical"/"create" + merged manifest content, `_diff_action` not called for existing CLAUDE.md → Task 2. ✅
- Update the existing `"overwrite"` assertion → Task 2 Step 1. ✅
- apply auto-overwrites "merge" paths (in place, not `.new`); other conflicts still `.new` → Task 3 (two tests). ✅
- `repo_write.py` unchanged → confirmed (no task touches it). ✅
- Gate + Smoke format parity → Task 4. ✅

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N"; every code step shows complete code. ✅

**3. Type/name consistency:**
- `merge_claude_md`, `MARKER` (Task 1) imported/used identically in Task 2 and the merge tests. ✅
- repo-plan uses `data = manifest.model_dump()` then mutates `data["files"]` dicts (`f["content"]`) — consistent with the `list[dict]` shape the client (`result["manifest"]["files"]`) and `write_pack_files` expect. ✅
- Plan action strings `"merge"` / `"identical"` / `"create"` / `"overwrite"` consistent across Task 2 (producer) and Task 3 (`apply` consumer filters `action == "merge"`). ✅
