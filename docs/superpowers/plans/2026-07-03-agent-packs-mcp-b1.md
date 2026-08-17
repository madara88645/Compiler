# Agent Packs B1 — Repo-Aware MCP Initializer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Agent Packs repo-aware and applyable via two MCP tools (`plan_agent_pack` / `apply_agent_pack`) — read the real repo, generate a tailored Claude pack, preview a diff, and write it locally (never clobbering existing files) — and fix the `risk_mode` → `settings.json` bug so strict is actually stricter.

**Architecture (locked):** The MCP server is a **pure HTTP client** (cannot import `app`). Therefore **all filesystem I/O happens client-side in the MCP process**; the FastAPI backend stays pure (repo facts in → pack + diff out, never touches disk). `app/repo_inspect/` derives a `RepoContext` from *collected file contents* (pure, no FS reads). A new `/agent-packs/claude/repo-plan` endpoint generates the pack + diff. MCP tools collect facts, call the endpoint, and (on apply) write files locally with a no-clobber policy.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest (backend); FastMCP + httpx (MCP server, `integrations/mcp-server/`).

**Non-goals (B1):** No web/frontend changes (B2). No standalone CLI / GitHub vehicle (B3). Not rendering the currently-dead IR fields (B3). No new cloud provider; OpenRouter-only rule unchanged.

---

## File Structure

- **New — backend core (pure):**
  - `app/repo_inspect/__init__.py` — public API: `RepoFacts`, `RepoContext`, `derive_repo_context(facts)`.
  - `app/repo_inspect/models.py` — dataclasses: `DetectedCommand`, `StackInfo`, `RepoContext`; Pydantic `RepoFacts` (the wire payload).
  - `app/repo_inspect/detect.py` — pure parsers: `parse_package_json_scripts`, `parse_makefile_targets`, `parse_pyproject`, `detect_stacks`.
  - `tests/test_repo_inspect.py`
- **New — backend route:**
  - `api/routes/agent_packs.py` (modify) — add `POST /agent-packs/claude/repo-plan`.
  - `tests/test_agent_packs_repo_plan.py`
- **New — MCP client:**
  - `integrations/mcp-server/repo_collect.py` — local: collect `RepoFacts` from a path (read manifest allowlist + shallow tree + existing CLAUDE.md/.claude).
  - `integrations/mcp-server/repo_write.py` — local: write manifest files with no-clobber.
  - `integrations/mcp-server/server.py` (modify) — add `plan_agent_pack` / `apply_agent_pack` tools.
  - `integrations/mcp-server/test_repo_collect.py`, `integrations/mcp-server/test_repo_write.py`, and additions to `integrations/mcp-server/test_server.py`.
- **Modified — generator (repo-aware + risk_mode fix):**
  - `app/adapters/agent_ir.py` — add `strict_permissions: bool = False` to `AgentExportIR`.
  - `app/adapters/agent_packs.py` — add optional repo fields to `AgentPackRequest`; set `strict_permissions`/`permission_mode` from `risk_mode`; thread detected commands/stack into brief + IR.
  - `app/adapters/claude_code.py` — `_project_settings_json` tightens when strict; `_project_claude_md` lists discovered commands.

---

## Task 1: `app/repo_inspect/` — pure RepoContext derivation

**Files:** Create `app/repo_inspect/__init__.py`, `app/repo_inspect/models.py`, `app/repo_inspect/detect.py`; Test `tests/test_repo_inspect.py`.

Design note: everything is **pure over content strings** (no `open()`, no `subprocess`) so it is trivially testable and safe to run on the backend. The MCP client collects raw file contents and a shallow tree; this module parses them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_repo_inspect.py`:

```python
from app.repo_inspect import RepoFacts, derive_repo_context


def _facts(files, tree=None, has_claude_md=False):
    return RepoFacts(files=files, tree=tree or list(files.keys()),
                     has_claude_md=has_claude_md, has_claude_dir=False)


def test_detects_node_stack_and_scripts():
    facts = _facts({"web/package.json": '{"scripts": {"test": "vitest run", "build": "next build", "lint": "eslint ."}}'})
    ctx = derive_repo_context(facts)
    assert "javascript" in {s.language for s in ctx.stacks}
    cmds = {c.name: c.command for c in ctx.commands}
    assert cmds["test"] == "npm run test"
    assert cmds["build"] == "npm run build"
    assert any(c.source.endswith("package.json") for c in ctx.commands)


def test_detects_python_pyproject_and_makefile():
    facts = _facts({
        "pyproject.toml": '[project]\nname = "x"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        "Makefile": "test:\n\tpython -m pytest tests/ -q\nbuild:\n\techo build\n",
    })
    ctx = derive_repo_context(facts)
    assert "python" in {s.language for s in ctx.stacks}
    cmds = {c.name: c.command for c in ctx.commands}
    assert cmds["test"] == "python -m pytest tests/ -q"  # Makefile target body wins for test


def test_empty_repo_is_safe():
    ctx = derive_repo_context(_facts({}))
    assert ctx.stacks == []
    assert ctx.commands == []


def test_surfaces_existing_claude_md():
    ctx = derive_repo_context(_facts({"CLAUDE.md": "# guide"}, has_claude_md=True))
    assert ctx.has_existing_claude_md is True
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_repo_inspect.py -q`
Expected: FAIL — `app.repo_inspect` not importable.

- [ ] **Step 3: Implement `app/repo_inspect/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class RepoFacts(BaseModel):
    """Raw repository facts collected client-side (contents only; no paths read here)."""

    files: dict[str, str] = Field(default_factory=dict)  # repo-relative path -> content
    tree: list[str] = Field(default_factory=list)         # shallow list of top-level entries
    has_claude_md: bool = False
    has_claude_dir: bool = False


@dataclass(frozen=True)
class DetectedCommand:
    name: str      # "test" | "build" | "lint" | "dev" | "format"
    command: str   # e.g. "npm run test", "python -m pytest tests/ -q"
    source: str    # e.g. "web/package.json", "Makefile"


@dataclass(frozen=True)
class StackInfo:
    language: str            # "python" | "javascript" | "go" | "rust" | ...
    frameworks: tuple[str, ...] = ()


@dataclass
class RepoContext:
    stacks: list[StackInfo] = field(default_factory=list)
    commands: list[DetectedCommand] = field(default_factory=list)
    has_existing_claude_md: bool = False
    has_existing_claude_dir: bool = False
    tree: list[str] = field(default_factory=list)

    def command_map(self) -> dict[str, str]:
        """First detected command per name, for templating."""
        out: dict[str, str] = {}
        for c in self.commands:
            out.setdefault(c.name, c.command)
        return out

    def stack_summary(self) -> str:
        langs = ", ".join(sorted({s.language for s in self.stacks}))
        fws = ", ".join(sorted({f for s in self.stacks for f in s.frameworks}))
        return " / ".join(p for p in (langs, fws) if p)
```

- [ ] **Step 4: Implement `app/repo_inspect/detect.py`**

```python
from __future__ import annotations

import json
import re

from .models import DetectedCommand, StackInfo

# Which manifest basenames imply which language.
_LANG_BY_MANIFEST = {
    "package.json": "javascript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    "Gemfile": "ruby",
}

# npm script name -> canonical command name we care about.
_NPM_SCRIPT_ALIASES = {
    "test": "test", "build": "build", "lint": "lint", "dev": "dev",
    "format": "format", "fmt": "format", "start": "dev",
}
_MAKE_TARGET_ALIASES = {
    "test": "test", "build": "build", "lint": "lint", "dev": "dev",
    "format": "format", "fmt": "format",
}


def parse_package_json_scripts(content: str, source: str) -> list[DetectedCommand]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    scripts = data.get("scripts") or {}
    if not isinstance(scripts, dict):
        return []
    cmds: list[DetectedCommand] = []
    for raw_name, canonical in _NPM_SCRIPT_ALIASES.items():
        if raw_name in scripts:
            cmds.append(DetectedCommand(name=canonical, command=f"npm run {raw_name}", source=source))
    return cmds


def parse_makefile_targets(content: str, source: str) -> list[DetectedCommand]:
    cmds: list[DetectedCommand] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)", line)
        if not m:
            continue
        target = m.group(1)
        canonical = _MAKE_TARGET_ALIASES.get(target)
        if not canonical:
            continue
        # Prefer the first recipe line (tab-indented) as the concrete command.
        recipe = ""
        for follow in lines[i + 1:]:
            if follow.startswith("\t"):
                recipe = follow.strip()
                break
            if follow.strip() and not follow.startswith("\t"):
                break
        cmds.append(DetectedCommand(name=canonical, command=recipe or f"make {target}", source=source))
    return cmds


def detect_stacks(files: dict[str, str]) -> list[StackInfo]:
    langs: dict[str, set[str]] = {}
    for path, content in files.items():
        base = path.rsplit("/", 1)[-1]
        lang = _LANG_BY_MANIFEST.get(base)
        if not lang:
            continue
        fw = langs.setdefault(lang, set())
        low = content.lower()
        for name in ("fastapi", "django", "flask", "next", "react", "vue", "svelte", "express", "nestjs"):
            if name in low:
                fw.add(name)
    return [StackInfo(language=lang, frameworks=tuple(sorted(fws))) for lang, fws in sorted(langs.items())]
```

- [ ] **Step 5: Implement `app/repo_inspect/__init__.py`**

```python
from __future__ import annotations

from .detect import detect_stacks, parse_makefile_targets, parse_package_json_scripts
from .models import DetectedCommand, RepoContext, RepoFacts, StackInfo

__all__ = ["RepoFacts", "RepoContext", "DetectedCommand", "StackInfo", "derive_repo_context"]

# Precedence: a Makefile 'test' target beats a package.json 'test' script, etc.
_SOURCE_PRIORITY = ("Makefile", "makefile", "pyproject.toml", "package.json")


def _source_rank(source: str) -> int:
    for i, needle in enumerate(_SOURCE_PRIORITY):
        if source.endswith(needle):
            return i
    return len(_SOURCE_PRIORITY)


def derive_repo_context(facts: RepoFacts) -> RepoContext:
    commands: list[DetectedCommand] = []
    for path, content in facts.files.items():
        base = path.rsplit("/", 1)[-1]
        if base == "package.json":
            commands += parse_package_json_scripts(content, path)
        elif base in ("Makefile", "makefile"):
            commands += parse_makefile_targets(content, path)

    # Keep the highest-priority command per name.
    best: dict[str, DetectedCommand] = {}
    for c in sorted(commands, key=lambda c: _source_rank(c.source)):
        best.setdefault(c.name, c)

    return RepoContext(
        stacks=detect_stacks(facts.files),
        commands=list(best.values()),
        has_existing_claude_md=facts.has_claude_md,
        has_existing_claude_dir=facts.has_claude_dir,
        tree=list(facts.tree),
    )
```

- [ ] **Step 6: Run tests to verify pass**

Run: `python -m pytest tests/test_repo_inspect.py -q`
Expected: PASS (4 tests). Adjust `_MAKE_TARGET_ALIASES`/precedence if the pyproject-vs-Makefile test needs tuning.

- [ ] **Step 7: Commit**

```bash
git add app/repo_inspect tests/test_repo_inspect.py
git commit -m "feat(repo-inspect): pure content-based RepoContext derivation"
```

---

## Task 2: Fix `risk_mode` → `settings.json` (strict is actually stricter)

**Files:** Modify `app/adapters/agent_ir.py`, `app/adapters/agent_packs.py`, `app/adapters/claude_code.py`; Test `tests/test_agent_packs_risk_mode.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_packs_risk_mode.py`:

```python
import json

from app.adapters.agent_packs import AgentPackRequest, ClaudeAgentPackAdapter


class _StubCompiler:
    def generate_agent(self, *a, **k):
        return ""  # force request-grounded IR (no generator dependency)

    def generate_skill(self, *a, **k):
        return ""


def _settings(risk_mode):
    req = AgentPackRequest(project_type="svc", stack="Python, FastAPI",
                           goal="Do a thing", pack_type="project-pack", risk_mode=risk_mode)
    manifest = ClaudeAgentPackAdapter().build_manifest(req, _StubCompiler())
    settings = next(f.content for f in manifest.files if f.path.endswith("settings.json"))
    return json.loads(settings)


def test_strict_settings_are_tighter_than_balanced():
    balanced = _settings("balanced")
    strict = _settings("strict")

    assert strict != balanced
    # strict uses a non-auto-accept default
    assert strict["permissions"]["defaultMode"] != "acceptEdits"
    assert balanced["permissions"]["defaultMode"] == "acceptEdits"
    # deploy/push CLIs are hard-denied under strict, merely asked under balanced
    assert "Bash(git push:*)" in strict["permissions"]["deny"]
    assert "Bash(git push:*)" in balanced["permissions"]["ask"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_agent_packs_risk_mode.py -q`
Expected: FAIL — strict and balanced settings are currently identical.

- [ ] **Step 3: Add `strict_permissions` to `AgentExportIR`**

In `app/adapters/agent_ir.py`, in the `AgentExportIR` dataclass (near line 53 where `permission_mode: str = "acceptEdits"` is defined), add:

```python
    strict_permissions: bool = False
```

- [ ] **Step 4: Set it from `risk_mode` in `_build_agent_ir`**

In `app/adapters/agent_packs.py`, in `_build_agent_ir` just before `return grounded` (currently line ~318-320, after the `pr-reviewer` block):

```python
    if req.risk_mode == "strict":
        grounded.permission_mode = "default"  # ask before edits, vs "acceptEdits"
        grounded.strict_permissions = True
    if req.pack_type == "pr-reviewer":
        grounded.allowed_tools = ["Read", "Glob", "Grep", "Bash"]
    return grounded
```

(Replace the existing `if req.pack_type == "pr-reviewer": ...; return grounded` tail with the block above so both apply.)

- [ ] **Step 5: Tighten `_project_settings_json` under strict**

In `app/adapters/claude_code.py`, replace `_project_settings_json` (lines 267–289) with:

```python
def _project_settings_json(ir: AgentExportIR) -> str:
    deny = [
        "Read(./.env)",
        "Read(./.env.*)",
        "Read(./**/.env)",
        "Read(./**/.env.*)",
        "Read(./secrets/**)",
        "Read(./**/*.pem)",
        "Read(./**/*.key)",
    ]
    ask = [
        "Bash(git push:*)",
        "Bash(git commit:*)",
        "Bash(fly:*)",
        "Bash(vercel:*)",
        "Bash(kubectl:*)",
    ]
    if ir.strict_permissions:
        # Strict: the deploy/push/commit gate becomes a hard deny, plus network egress guards.
        deny = deny + ask + ["WebFetch", "Bash(curl:*)", "Bash(rm -rf:*)"]
        ask = ["Bash(git:*)", "Bash(npm:*)", "Bash(pip:*)"]
    settings: dict[str, Any] = {
        "permissions": {
            "defaultMode": ir.permission_mode,
            "deny": deny,
            "ask": ask,
        }
    }
    return json.dumps(settings, indent=2)
```

- [ ] **Step 6: Run test to verify pass**

Run: `python -m pytest tests/test_agent_packs_risk_mode.py -q`
Expected: PASS.

- [ ] **Step 7: Run the existing agent-packs suite (no regressions)**

Run: `python -m pytest tests/test_agent_packs_api.py tests/test_agent_packs*.py -q`
Expected: PASS (update any test that asserted strict == balanced settings).

- [ ] **Step 8: Commit**

```bash
git add app/adapters/agent_ir.py app/adapters/agent_packs.py app/adapters/claude_code.py tests/test_agent_packs_risk_mode.py
git commit -m "fix(agent-packs): strict risk_mode produces genuinely tighter settings.json"
```

---

## Task 3: Repo-aware generation (real commands in CLAUDE.md)

**Files:** Modify `app/adapters/agent_packs.py`, `app/adapters/claude_code.py`; Test `tests/test_agent_packs_repo_aware.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_packs_repo_aware.py`:

```python
from app.adapters.agent_packs import AgentPackRequest, ClaudeAgentPackAdapter


class _StubCompiler:
    def generate_agent(self, *a, **k):
        return ""

    def generate_skill(self, *a, **k):
        return ""


def test_detected_commands_land_in_claude_md():
    req = AgentPackRequest(
        project_type="svc", stack="Python, FastAPI", goal="Add a health route",
        pack_type="project-pack", risk_mode="balanced",
        detected_commands={"test": "python -m pytest tests/ -q", "build": "next build"},
        detected_stack="python / fastapi, next",
    )
    manifest = ClaudeAgentPackAdapter().build_manifest(req, _StubCompiler())
    claude_md = next(f.content for f in manifest.files if f.path == "CLAUDE.md")
    assert "python -m pytest tests/ -q" in claude_md
    assert "next build" in claude_md
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_agent_packs_repo_aware.py -q`
Expected: FAIL — request has no `detected_commands` field yet.

- [ ] **Step 3: Add optional repo fields to `AgentPackRequest`**

In `app/adapters/agent_packs.py`, extend the model (lines 28–34):

```python
class AgentPackRequest(BaseModel):
    project_type: str = Field(..., min_length=1, max_length=120)
    stack: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=8_000)
    pack_type: PackType
    risk_mode: RiskMode = "balanced"
    detected_commands: dict[str, str] | None = None
    detected_stack: str | None = None
    has_existing_claude_md: bool = False
```

- [ ] **Step 4: Thread detected commands into the IR workflows**

In `app/adapters/agent_packs.py` `_build_agent_ir`, replace the generic discovery workflow line (currently lines 300–303, the "Discover the repository's existing validation commands..." entry) with a real-commands line when available:

```python
            _validation_workflow(req),
```

and add this helper near the other `_build_*` helpers:

```python
def _validation_workflow(req: AgentPackRequest) -> str:
    cmds = req.detected_commands or {}
    if cmds:
        pairs = ", ".join(f"{name}: `{cmd}`" for name, cmd in cmds.items())
        return (
            f"Run the repository's real validation commands ({pairs}); "
            "report commands, results, remaining risk, and files changed."
        )
    return (
        "Discover the repository's existing validation commands, run the smallest relevant checks, "
        "and report commands, results, remaining risk, and files changed."
    )
```

- [ ] **Step 5: Surface a "Discovered validation commands" section in CLAUDE.md**

Pass detected commands to the CLAUDE.md builder. In `app/adapters/claude_code.py`, change `_project_claude_md` to accept detected commands and render a section. Since the emitter chain passes only `ir`, carry the commands on the IR: add `detected_commands: dict[str, str] = field(default_factory=dict)` to `AgentExportIR` (in `agent_ir.py`), set it in `_build_agent_ir`:

```python
    grounded.detected_commands = req.detected_commands or {}
```

Then in `_project_claude_md` (claude_code.py), after the `## Validation contract` block, append when present:

```python
    discovered = ""
    if ir.detected_commands:
        lines = "\n".join(f"- {name}: `{cmd}`" for name, cmd in ir.detected_commands.items())
        discovered = f"\n\n## Discovered validation commands\n\n{lines}"
```

and insert `{discovered}` into the returned template right after the Validation contract section.

- [ ] **Step 6: Use `detected_stack` in the brief (optional enrichment)**

In `_build_agent_brief`, when `req.detected_stack` is set, prefer it:

```python
    stack_line = req.detected_stack or req.stack
```

and use `stack_line` in the `f"Stack: {...}"` line.

- [ ] **Step 7: Run tests to verify pass**

Run: `python -m pytest tests/test_agent_packs_repo_aware.py tests/test_agent_packs_risk_mode.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/adapters/agent_ir.py app/adapters/agent_packs.py app/adapters/claude_code.py tests/test_agent_packs_repo_aware.py
git commit -m "feat(agent-packs): thread detected repo commands/stack into generated pack"
```

---

## Task 4: Backend route `POST /agent-packs/claude/repo-plan`

**Files:** Modify `api/routes/agent_packs.py`; Test `tests/test_agent_packs_repo_plan.py`.

The endpoint is **pure**: it accepts collected `RepoFacts` + pack params, derives context, generates the manifest, and computes a diff against the existing files the client included. It never touches disk.

- [ ] **Step 1: Write the failing API test**

Create `tests/test_agent_packs_repo_plan.py`:

```python
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_repo_plan_returns_manifest_and_diffs():
    body = {
        "pack_type": "project-pack",
        "goal": "Add a health route",
        "risk_mode": "strict",
        "repo_facts": {
            "files": {"package.json": '{"scripts": {"test": "vitest run"}}',
                       "CLAUDE.md": "# existing guide"},
            "tree": ["package.json", "CLAUDE.md", "src"],
            "has_claude_md": True,
            "has_claude_dir": False,
        },
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["manifest"]["pack_type"] == "project-pack"
    # CLAUDE.md already exists -> flagged as an overwrite in the plan
    claude = next(p for p in data["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "overwrite"
    # a brand-new file is a create
    assert any(p["action"] == "create" for p in data["plan"])
    # detected npm test command surfaced
    assert "npm run test" in str(data["detected"]["commands"])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_agent_packs_repo_plan.py -q`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Implement the route**

In `api/routes/agent_packs.py`, add (reusing the existing `_get_compiler` / adapter pattern already in that file):

```python
from pydantic import BaseModel

from app.repo_inspect import RepoFacts, derive_repo_context
from app.adapters.agent_packs import AGENT_PACK_ADAPTERS, AgentPackRequest


class RepoPlanRequest(BaseModel):
    pack_type: str
    goal: str
    risk_mode: str = "balanced"
    project_type: str = "repository"
    repo_facts: RepoFacts


def _diff_action(existing: dict[str, str], path: str, content: str) -> str:
    if path not in existing:
        return "create"
    return "identical" if existing[path] == content else "overwrite"


@router.post("/agent-packs/claude/repo-plan")
def repo_plan_claude_agent_pack(req: RepoPlanRequest) -> dict:
    ctx = derive_repo_context(req.repo_facts)
    pack_req = AgentPackRequest(
        project_type=req.project_type,
        stack=ctx.stack_summary() or "unspecified",
        goal=req.goal,
        pack_type=req.pack_type,  # validated by the Literal in AgentPackRequest
        risk_mode=req.risk_mode,
        detected_commands=ctx.command_map() or None,
        detected_stack=ctx.stack_summary() or None,
        has_existing_claude_md=ctx.has_existing_claude_md,
    )
    manifest = AGENT_PACK_ADAPTERS["claude"].build_manifest(pack_req, _get_compiler())
    existing = req.repo_facts.files
    plan = [
        {"path": f.path, "action": _diff_action(existing, f.path, f.content)}
        for f in manifest.files
    ]
    return {
        "manifest": manifest.model_dump(),
        "plan": plan,
        "detected": {
            "stack": ctx.stack_summary(),
            "commands": ctx.command_map(),
            "has_existing_claude_md": ctx.has_existing_claude_md,
        },
    }
```

(If `_get_compiler` is imported differently in this module, follow the existing pattern already used by `build_claude_agent_pack`.)

- [ ] **Step 4: Run the test to verify pass**

Run: `python -m pytest tests/test_agent_packs_repo_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routes/agent_packs.py tests/test_agent_packs_repo_plan.py
git commit -m "feat(api): repo-plan endpoint generates repo-aware pack + diff (no disk writes)"
```

---

## Task 5: MCP client — collector, writer, and `plan`/`apply` tools

**Files:** Create `integrations/mcp-server/repo_collect.py`, `integrations/mcp-server/repo_write.py`, `integrations/mcp-server/test_repo_collect.py`, `integrations/mcp-server/test_repo_write.py`; Modify `integrations/mcp-server/server.py`, `integrations/mcp-server/test_server.py`.

### 5a: Local collector

- [ ] **Step 1: Write the failing test**

Create `integrations/mcp-server/test_repo_collect.py`:

```python
from pathlib import Path

from repo_collect import collect_repo_facts


def test_collects_manifests_tree_and_claude(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    (tmp_path / "CLAUDE.md").write_text("# guide")
    (tmp_path / "src").mkdir()
    (tmp_path / ".env").write_text("SECRET=xyz")

    facts = collect_repo_facts(str(tmp_path))

    assert "package.json" in facts["files"]
    assert facts["has_claude_md"] is True
    assert "src" in facts["tree"]
    assert ".env" not in facts["files"]  # never collect secrets
```

- [ ] **Step 2: Run to verify failure**

Run: `cd integrations/mcp-server && python -m pytest test_repo_collect.py -q`
Expected: FAIL — no `repo_collect` module.

- [ ] **Step 3: Implement `repo_collect.py`**

```python
from __future__ import annotations

import os

# Small allowlist of non-secret manifest/config files worth sending to the backend.
_MANIFEST_FILES = (
    "package.json", "pyproject.toml", "requirements.txt", "setup.py", "Pipfile",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "composer.json", "Gemfile",
    "Makefile", "makefile", "tox.ini", "setup.cfg",
)
_MAX_BYTES = 64_000  # never read large files


def _read(path: str) -> str | None:
    try:
        if os.path.getsize(path) > _MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def collect_repo_facts(repo_path: str) -> dict:
    files: dict[str, str] = {}
    # top-level manifests + one level down (e.g. web/package.json)
    for rel in _MANIFEST_FILES:
        content = _read(os.path.join(repo_path, rel))
        if content is not None:
            files[rel] = content
    try:
        for entry in sorted(os.listdir(repo_path)):
            sub = os.path.join(repo_path, entry)
            if os.path.isdir(sub) and not entry.startswith("."):
                for rel in _MANIFEST_FILES:
                    content = _read(os.path.join(sub, rel))
                    if content is not None:
                        files[f"{entry}/{rel}"] = content
    except OSError:
        pass

    claude_md = os.path.join(repo_path, "CLAUDE.md")
    if os.path.isfile(claude_md):
        content = _read(claude_md)
        if content is not None:
            files["CLAUDE.md"] = content

    try:
        tree = sorted(os.listdir(repo_path))
    except OSError:
        tree = []

    return {
        "files": files,
        "tree": tree,
        "has_claude_md": os.path.isfile(claude_md),
        "has_claude_dir": os.path.isdir(os.path.join(repo_path, ".claude")),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd integrations/mcp-server && python -m pytest test_repo_collect.py -q`
Expected: PASS.

### 5b: Local writer (no-clobber)

- [ ] **Step 5: Write the failing test**

Create `integrations/mcp-server/test_repo_write.py`:

```python
from pathlib import Path

from repo_write import write_pack_files


def test_creates_new_and_never_clobbers(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("OLD")
    files = [
        {"path": "CLAUDE.md", "content": "NEW"},
        {"path": ".claude/settings.json", "content": "{}"},
    ]

    result = write_pack_files(str(tmp_path), files, overwrite=[])

    assert (tmp_path / ".claude/settings.json").read_text() == "{}"   # created
    assert (tmp_path / "CLAUDE.md").read_text() == "OLD"               # NOT clobbered
    assert (tmp_path / "CLAUDE.md.new").read_text() == "NEW"           # written aside
    assert result["created"] == [".claude/settings.json"]
    assert result["conflicts"] == ["CLAUDE.md"]


def test_overwrite_list_allows_replacement(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("OLD")
    result = write_pack_files(str(tmp_path), [{"path": "CLAUDE.md", "content": "NEW"}], overwrite=["CLAUDE.md"])
    assert (tmp_path / "CLAUDE.md").read_text() == "NEW"
    assert result["overwritten"] == ["CLAUDE.md"]
```

- [ ] **Step 6: Implement `repo_write.py`**

```python
from __future__ import annotations

import os


def _safe_join(root: str, rel: str) -> str:
    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, rel))
    if os.path.commonpath([root_abs, target]) != root_abs:
        raise ValueError(f"unsafe path escapes repo root: {rel}")
    return target


def write_pack_files(repo_path: str, files: list[dict], overwrite: list[str]) -> dict:
    created: list[str] = []
    overwritten: list[str] = []
    conflicts: list[str] = []
    for f in files:
        rel, content = f["path"], f["content"]
        target = _safe_join(repo_path, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.exists(target):
            if rel in overwrite:
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(content)
                overwritten.append(rel)
            else:
                with open(target + ".new", "w", encoding="utf-8") as fh:
                    fh.write(content)
                conflicts.append(rel)
        else:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(content)
            created.append(rel)
    return {"created": created, "overwritten": overwritten, "conflicts": conflicts}
```

- [ ] **Step 7: Run to verify pass**

Run: `cd integrations/mcp-server && python -m pytest test_repo_write.py -q`
Expected: PASS.

### 5c: MCP tools

- [ ] **Step 8: Write the failing tool test**

Add to `integrations/mcp-server/test_server.py` (following the existing `_MockAsyncClient` pattern already in the file):

```python
def test_plan_agent_pack_posts_repo_facts(tmp_path, monkeypatch):
    import server
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    mock = _MockAsyncClient({"manifest": {"files": []}, "plan": [], "detected": {}})
    monkeypatch.setattr(server.httpx, "AsyncClient", lambda *a, **k: mock)

    result = asyncio.run(server.plan_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    assert mock.calls[0][0].endswith("/agent-packs/claude/repo-plan")
    body = mock.calls[0][1]
    assert "package.json" in body["repo_facts"]["files"]
    assert "plan" in result
```

(Match the exact `_MockAsyncClient` signature/return shape already used in `test_server.py`.)

- [ ] **Step 9: Implement the tools in `server.py`**

Add near the other `@mcp.tool()` functions (reuse the existing base-URL/httpx pattern in the file):

```python
from repo_collect import collect_repo_facts
from repo_write import write_pack_files


@mcp.tool()
async def plan_agent_pack(pack_type: str, goal: str = "", risk_mode: str = "balanced", path: str = ".") -> dict:
    """Preview a repo-aware Claude agent pack for the local repository (writes nothing).

    Reads the repo at `path`, generates a tailored pack, and returns the file plan with
    create/overwrite actions against existing files, plus detected stack and commands.
    """
    facts = collect_repo_facts(path)
    body = {"pack_type": pack_type, "goal": goal, "risk_mode": risk_mode, "repo_facts": facts}
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/agent-packs/claude/repo-plan", json=body, timeout=60.0)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def apply_agent_pack(pack_type: str, goal: str = "", risk_mode: str = "balanced",
                           path: str = ".", overwrite: list[str] | None = None) -> dict:
    """Generate and WRITE a repo-aware Claude agent pack into the local repository.

    Existing files are never silently overwritten: a conflicting path is written as
    `<path>.new` unless its path is included in `overwrite` (which the plan surfaces).
    """
    facts = collect_repo_facts(path)
    body = {"pack_type": pack_type, "goal": goal, "risk_mode": risk_mode, "repo_facts": facts}
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/agent-packs/claude/repo-plan", json=body, timeout=60.0)
        resp.raise_for_status()
        manifest = resp.json()["manifest"]
    written = write_pack_files(path, manifest["files"], overwrite or [])
    return {"written": written, "plan": resp.json()["plan"]}
```

(Use the module's existing backend-URL constant — the map shows config comes from `compile_settings.py` env vars; match whatever `server.py` already uses for the base URL, e.g. `BACKEND_URL`.)

- [ ] **Step 10: Run the MCP tests**

Run: `cd integrations/mcp-server && python -m pytest test_repo_collect.py test_repo_write.py test_server.py -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add integrations/mcp-server/repo_collect.py integrations/mcp-server/repo_write.py \
        integrations/mcp-server/server.py integrations/mcp-server/test_repo_collect.py \
        integrations/mcp-server/test_repo_write.py integrations/mcp-server/test_server.py
git commit -m "feat(mcp): plan_agent_pack / apply_agent_pack repo-aware tools with no-clobber writes"
```

---

## Task 6: Full verification

- [ ] **Step 1: Backend suite**

Run: `python -m pytest tests/ -q`
Expected: pass (pre-existing network-dependent `test_validate_summary_and_api_schemas` may fail locally — unrelated).

- [ ] **Step 2: MCP suite**

Run: `cd integrations/mcp-server && python -m pytest -q`
Expected: pass.

- [ ] **Step 3: Manual smoke (recommended)**

Start the backend (`python -m uvicorn api.main:app --port 8000`), run the MCP server, and from a Claude Code / Cursor session call `plan_agent_pack("project-pack", goal="...")` in a real repo; confirm the plan lists creates/overwrites and detected commands, then `apply_agent_pack(..., overwrite=["CLAUDE.md"])` writes files with no-clobber.

---

## Self-Review

**Spec coverage (2026-07-03-agent-packs-mcp-repo-aware-design.md):**
- `app/repo_inspect/` pure core → Task 1. ✅ (content-based, not path-reading, because MCP—not the backend—owns FS I/O).
- Reuse existing generator, feed real facts → Task 3. ✅
- `plan` / `apply` MCP tools, preview→confirm→write, never silently overwrite → Task 5 (writer + tools). ✅
- `risk_mode` → `settings.json` fix → Task 2. ✅
- No web changes (B2), no CLI/GitHub (B3), no dead-IR rendering (B3) → not in any task. ✅
- Plan-time verification (MCP imports app vs HTTP): resolved — MCP is HTTP-only, so FS I/O is client-side and the backend stays pure (new `/repo-plan` endpoint). ✅ (This refines the spec's assumption.)

**Placeholder scan:** New modules have full code. Threading edits (Task 3 Step 4–6, Task 4 Step 3) reference exact functions/lines and give the code to insert; a couple note "match the existing pattern in this file" for the compiler accessor / backend-URL constant — these are real, named anchors, not TBDs.

**Type consistency:** `RepoFacts` (Pydantic) is the wire model used identically by the collector output, the endpoint body, and `derive_repo_context`. `RepoContext.command_map()` returns `dict[str,str]`, matching `AgentPackRequest.detected_commands`. `AgentExportIR` gains `strict_permissions: bool` (Task 2) and `detected_commands: dict[str,str]` (Task 3), both read in `claude_code.py`. The MCP tools post to `/agent-packs/claude/repo-plan`, the exact path the endpoint (Task 4) registers.
