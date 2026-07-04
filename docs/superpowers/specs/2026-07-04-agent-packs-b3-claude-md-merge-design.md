# Agent Packs B3 (slice 2) — CLAUDE.md Smart Merge (Design)

- **Date:** 2026-07-04
- **Status:** Approved (design), pending spec review
- **Branch:** `feat/agent-packs-claude-md-merge` (off `main`, which now includes B1 / #933)
- **Surface:** `app/repo_inspect/`, `api/routes/agent_packs.py` (repo-plan), and
  `integrations/mcp-server/server.py` (apply). No web change.

## Problem

B1's repo-aware apply path writes generated files into a real repo with a **no-clobber**
policy: an existing path not in the `overwrite` list is written to `<path>.new`
(`integrations/mcp-server/repo_write.py:27-35`). So when a repo already has a `CLAUDE.md`,
the generated guidance lands as `CLAUDE.md.new` and the user must hand-merge it.

`repo-plan` already receives the repo's existing files (`req.repo_facts.files: dict[str,
str]`, path → content) **and** the generated `CLAUDE.md`, and classifies each file as
create / identical / overwrite (`_diff_action`, `api/routes/agent_packs.py:64-67`). This
slice adds a **merge** path for `CLAUDE.md`. (Second of the remaining B3 slices; B1 is
merged, so this apply path is on `main`.)

## Goals / Non-goals

**Goals:** when the repo already has a `CLAUDE.md`, non-destructively merge the generated
guidance into it — preserve the user's existing content and append only the generated `##`
sections whose heading the user doesn't already have — and apply that merge in place.

**Non-goals / accepted limitations:**
- The web download path (no repo, no existing file) — unchanged.
- Any file other than exactly `CLAUDE.md` — settings.json / `.mcp.json` / hooks.example /
  agents keep create/overwrite/identical/`.new`.
- **Same-heading, different body is not merged** (see Risks): if the user already has `##
  Security`, a generated `## Security` with a richer body is *intentionally dropped*. Body-
  diff-aware merge is a follow-up.
- Sub-section (`###`) / line-level / three-way merge.
- No `.env`/auth/deploy/secret changes.

## Approved decisions

- **Strategy A — section-aware, append-new-only, idempotent** (user decision).
- **Merge logic in the pure backend** (matches B1: FastAPI pure — repo facts in → pack +
  plan out; MCP client owns disk I/O).
- **Merge applied in place** — a section-append merge is non-destructive by construction.

## Design

### 1. Pure merge — `app/repo_inspect/claude_md_merge.py`

The whole algorithm is pinned below so two implementers produce byte-identical output.

```python
import re

MARKER = "<!-- Added by Prompt Compiler: sections not already in your CLAUDE.md -->"

_HEADING_RE = re.compile(r"^##[ \t]+(.+?)\s*$")   # level-2 only; "##Foo" (no space) is NOT a heading
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")          # >=3 backticks or tildes after leading whitespace


def _heading_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _iter_sections(md: str) -> list[tuple[str, str]]:
    """(heading_key, section_text) for each level-2 section, fence-aware.

    A section's text is the ``## `` line plus every following line up to (but not
    including) the next level-2 heading or EOF, joined with "\\n". A ``## `` line inside a
    fenced code block is body, not a heading. Fences opened by ``` close only on ``` (same
    char, >= run length); likewise ~~~.
    """
    lines = md.splitlines()
    fence: tuple[str, int] | None = None
    out: list[tuple[str, str]] = []
    key: str | None = None
    buf: list[str] = []
    for line in lines:
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
    seen = {k for k, _ in _iter_sections(existing)}   # existing headings (fence-aware)
    new_sections: list[str] = []
    for key, text in _iter_sections(generated):
        if key in seen:          # already in the user's file OR already chosen this run
            continue
        seen.add(key)            # de-dupe within generated too (keep first)
        new_sections.append(text.rstrip())
    if not new_sections:
        return existing
    return existing.rstrip() + "\n\n" + MARKER + "\n\n" + "\n\n".join(new_sections) + "\n"
```

- **Preserved prefix:** the merged output starts with `existing.rstrip()` (trailing
  whitespace/newlines removed); the user's interior bytes — including any `\r\n` — are
  untouched (`existing` is prepended verbatim, never re-split). Trailing whitespace on the
  final existing line is the only thing normalized.
- **Idempotency (same `generated`):** after a merge, the appended sections' `## ` headings
  are in the output, and `MARKER` is a comment (not a heading), so
  `merge_claude_md(merge_claude_md(e, g), g) == merge_claude_md(e, g)`.
- **Matching keys drop the generated section** (accepted limitation above). **Duplicate
  keys within `generated`** collapse to the first (the `seen` set).
- **Preconditions:** the generator always emits `##`-sectioned CLAUDE.md
  (`_project_claude_md` / `_pr_reviewer_memory` — verified: Project context, Objectives,
  Constraints, Workflow, Declared technology context, Validation contract, Claude Code
  configuration). So "generated has no `##`" (→ return existing) does not occur for our
  generator; it is handled only for robustness.
- **Fence rationale:** today's *generated* CLAUDE.md has no triple-fenced blocks (only
  inline backticks), so fence-awareness is for the **user's existing** file (which may
  hand-author fenced `## ` lines) and for forward-safety.

### 2. `repo-plan` integration (pure) — `api/routes/agent_packs.py`

Replace the current plan-building (lines 103-107) with a CLAUDE.md-aware version that also
returns the merged content. Pin the mechanic: dump the manifest, mutate the dumped
`files`, and build the plan in the same pass. `_diff_action` is **not** called for the
`CLAUDE.md` path when `CLAUDE.md` exists in `existing`.

```python
existing = req.repo_facts.files
data = manifest.model_dump()
plan: list[dict] = []
for f in data["files"]:                       # f is a dict {"path", "content", "kind"}
    path, content = f["path"], f["content"]
    if path == "CLAUDE.md" and "CLAUDE.md" in existing:   # exact, case-sensitive
        merged = merge_claude_md(existing["CLAUDE.md"], content)
        f["content"] = merged                 # mutates the dict inside data["files"]
        plan.append({"path": path, "action": "identical" if merged == existing["CLAUDE.md"] else "merge"})
    else:
        plan.append({"path": path, "action": _diff_action(existing, path, content)})
return {"manifest": data, "plan": plan, "detected": {...unchanged...}}
```

`CLAUDE.md` not in `existing` → `_diff_action` returns `"create"` and content stays the
generated content (regression-safe vs B1).

### 3. `apply_agent_pack` integration — `integrations/mcp-server/server.py`

`apply_agent_pack` (server.py:165-183) currently passes the caller's `overwrite` straight
to `write_pack_files`. Add `"merge"`-action paths to the effective overwrite set (the
merged content is non-destructive, so writing in place is safe):

```python
result = await _post_json("/agent-packs/claude/repo-plan", payload)
merge_paths = [p["path"] for p in result["plan"] if p.get("action") == "merge"]
effective_overwrite = list(dict.fromkeys((overwrite or []) + merge_paths))
written = write_pack_files(path, result["manifest"]["files"], effective_overwrite)
return {"written": written, "plan": result["plan"]}
```

`repo_write.write_pack_files` is **unchanged**: a path in the overwrite set writes in place,
so the merged `CLAUDE.md` lands as `CLAUDE.md` (not `.new`), while other genuine conflicts
still `.new`. The `"merge"` action is visible in `plan_agent_pack` before applying.

## File-level impact

**New:** `app/repo_inspect/claude_md_merge.py`; `tests/test_claude_md_merge.py`.

**Changed:**
- `api/routes/agent_packs.py` — CLAUDE.md merge special-case in the repo-plan handler.
- `integrations/mcp-server/server.py` — `apply_agent_pack` merge-path auto-overwrite.
- `tests/test_agent_packs_repo_plan.py` — **update the existing assertion** at
  `test_repo_plan_returns_manifest_and_diffs` (currently asserts the differing `CLAUDE.md`
  is action `"overwrite"`, `~line 29`) to `"merge"`, plus new merge/identical/create cases.
- `integrations/mcp-server/test_server.py` — apply writes merge in place.

**Unchanged:** `integrations/mcp-server/repo_write.py`; `app/adapters/**`;
`app/repo_inspect/models.py`/`detect.py`; all web / plain-generate / download code.

## Testing

`tests/test_claude_md_merge.py` (pure, deterministic, byte-level):
- **preserve:** for a non-empty merge, `merged.startswith(existing.rstrip())` **and** the
  slice of `merged` before `"\n\n" + MARKER` equals `existing.rstrip()` exactly.
- **append-new-only:** a generated section whose heading exists in the user's file is not
  duplicated; a section the user lacks is appended after `MARKER`.
- **idempotent:** `merge(merge(e, g), g) == merge(e, g)`.
- **no-new → unchanged:** every generated heading already present → `merged == existing`.
- **same-key different-body drop (contract):** existing `## Security\nshort`, generated `##
  Security\nlong policy` → the long body is NOT appended (documents the accepted limitation).
- **dup within generated:** generated with `## Setup` and `## setup` (existing lacks it) →
  exactly one appended section.
- **edge:** existing with no `##` (append all generated sections); generated with no `##`
  (return existing); heading key is case/whitespace-insensitive (`## Objectives` vs `##
  objectives  ` collide); `##Foo` (no space) is not a heading.
- **fence-aware, both sides:** (i) a `## X` inside a ```` ``` ```` fence in `generated` is
  not treated as a heading; (ii) a `## Deploy` inside a fence in the **existing** file does
  not shadow a real generated `## Deploy` (it IS appended); (iii) a `~~~`-opened block
  containing a ```` ``` ```` line and a `## Y` line parses correctly (mixed delimiters).
- **CRLF preserved:** an existing file with `\r\n` line endings keeps them verbatim in the
  merged prefix.

`tests/test_agent_packs_repo_plan.py`:
- Update the existing differing-CLAUDE.md assertion to `action == "merge"`; assert the
  returned `manifest` `CLAUDE.md` content contains the existing content and `MARKER`.
- Existing `CLAUDE.md` already containing all generated headings → `action == "identical"`.
- No `CLAUDE.md` in repo_facts → `action == "create"` (regression).

`integrations/mcp-server/test_server.py` (reuse the existing `_MockAsyncClient` +
`patch("server.httpx.AsyncClient", return_value=client)` style, as in
`test_apply_agent_pack_writes_files`): a repo-plan response with a `CLAUDE.md` `"merge"`
action + an existing `CLAUDE.md` on disk → after `apply_agent_pack`, `CLAUDE.md` holds the
merged content and no `CLAUDE.md.new` exists; a separate genuinely-conflicting file still
produces `.new`.

**Gate before PR:** `python -m pytest tests/test_claude_md_merge.py tests/test_agent_packs_repo_plan.py -q`, then `python -m pytest integrations/mcp-server/ -q`, then `python -m pytest tests/ -q`. Format changed Python with `uvx ruff@0.1.14 format` before pushing (Smoke gate).

## Risks & mitigations

- **Corrupting the user's CLAUDE.md.** The merge only appends; interior bytes are preserved
  verbatim. Enforced by the `preserve` test (prefix-before-marker equals `existing.rstrip()`
  exactly) + the CRLF test.
- **Accepted content loss (same-key different-body, preamble-only generated).** Documented
  in Non-goals; the same-key-drop test makes it a conscious contract. Preamble-only-generated
  cannot occur for our generator (precondition above).
- **Fence mis-parse.** Marker-aware fence rule (char + run length) applied to both parses;
  mixed-delimiter test.
- **In-place write of a merge.** Safe (non-destructive); still surfaced as `"merge"` in
  `plan_agent_pack`.

## Out of scope / follow-ups

- Body-diff-aware merge for same-heading sections (append under a disambiguated heading).
- Merging other files (settings.json / `.mcp.json` / hooks) — they keep no-clobber `.new`.
- Web UI surfacing (web path has no existing repo file).
- Remaining B3 slices: CLI vehicle; GitHub-PR vehicle.
