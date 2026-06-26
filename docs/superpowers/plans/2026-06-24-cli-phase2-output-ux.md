# CLI Phase 2 — compile/pack Output & UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `promptc compile` show a readable summary card + rendered System/User/Plan/Expanded prompts by default (raw IR behind `--json-only`), centralize rich rendering in a new `cli/render.py`, add a metadata header to `pack`, fix the dead `--quiet` flag, and silence the noisy `[STRATEGIST]` stderr line.

**Architecture:** A new `cli/render.py` owns human-tier rich rendering. `_run_compile` (in `cli/commands/core.py`) stops gating the v2 emitter strings on `--render-v2` (which also fixes `--quiet`) and replaces its default raw-IR dump with a summary card + sections via `cli/render.py`. `pack` gains a metadata header passed into the existing `app/utils.py` renderers. One log-level fix in `app/agents/context_strategist.py`. Emitters/heuristics are untouched; machine-output paths (`--json-only`/`--out`/`--format`/`--quiet`) stay plain.

**Tech Stack:** Python 3.10+, Typer, Rich (`Console`/`Panel`/`rule`/`markup.escape`), pytest + `typer.testing.CliRunner` + `Console(record=True)`.

**Branch:** `feat/cli-phase2-output-ux` (exists; spec committed at `ff52b986`). One PR, four clean commits + a test-update/verify task.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `app/agents/context_strategist.py` | Agent 6 (RAG retrieval + query expansion) | Modify — line 101 `print`→`logger.debug` |
| `cli/render.py` | Human-tier CLI rendering helpers | **Create** |
| `cli/commands/core.py` | `_run_compile` + `pack_command` | Modify — default render via `cli/render.py`; pass pack header |
| `app/utils.py` | `_render_prompt_pack_md/txt` (CLI-only) | Modify — optional metadata header |
| `tests/test_cli_phase2.py` | New tests for all of the above | **Create** |
| Existing compile tests | Some assert default output is raw IR JSON | Update to use `--json-only` |

---

## Task 1: Silence the `[STRATEGIST]` query-expansion noise

**Files:**
- Modify: `app/agents/context_strategist.py` (imports + line 101)
- Test: `tests/test_cli_phase2.py` (new)

Context: `_expand_query` (line 77) calls the LLM; on any failure (e.g. no `OPENROUTER_API_KEY` → 401) it currently does `print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)` (line 101), which fires on every offline run and looks like an error. It already falls back gracefully to `_normalize_queries([], prompt)`. Downgrade to `logger.debug`, matching the rest of the codebase.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_phase2.py`:

```python
def test_strategist_expansion_failure_is_silent(capsys):
    from app.agents.context_strategist import ContextStrategist

    class _BoomClient:
        def _call_api(self, *args, **kwargs):
            raise RuntimeError("no api key")

    strat = ContextStrategist(client=_BoomClient())
    result = strat._expand_query("write a haiku about the sea")
    captured = capsys.readouterr()
    assert "[STRATEGIST]" not in captured.err
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_phase2.py::test_strategist_expansion_failure_is_silent -v`
Expected: FAIL — stderr contains `[STRATEGIST] Query expansion failed: no api key`.

- [ ] **Step 3: Add a module logger to `app/agents/context_strategist.py`**

After the existing imports (the block ending with `from app.llm_engine.client import WorkerClient`, line 10), add:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Replace the print with logger.debug**

At line 101, change:

```python
            print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)
```

to:

```python
            logger.debug("Query expansion failed: %s", e)
```

- [ ] **Step 5: Drop the now-possibly-unused `sys` import if ruff flags it**

Run: `python -m ruff check app/agents/context_strategist.py`
If it reports `F401` for `import sys` (line 7), remove that line. If `sys` is still used elsewhere in the file, leave it. Re-run ruff until clean.

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_cli_phase2.py::test_strategist_expansion_failure_is_silent -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/agents/context_strategist.py tests/test_cli_phase2.py
git commit -m "fix(cli): silence [STRATEGIST] query-expansion failures (logger.debug)"
```

---

## Task 2: Create `cli/render.py` (human-tier rendering helpers)

**Files:**
- Create: `cli/render.py`
- Test: `tests/test_cli_phase2.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_phase2.py`:

```python
from rich.console import Console

from cli.render import render_summary_card, render_prompt_sections


def test_summary_card_shows_key_fields():
    console = Console(record=True, width=80)
    ir = {
        "persona": "assistant",
        "domain": "software",
        "output_format": "text",
        "goals": ["g1"],
        "constraints": ["c1", "c2"],
        "metadata": {"policy_summary": {"risk_level": "low"}},
    }
    render_summary_card(console, ir)
    out = console.export_text()
    assert "assistant" in out
    assert "software" in out
    assert "low" in out


def test_prompt_sections_preserve_bracket_tokens():
    console = Console(record=True, width=80)
    render_prompt_sections(console, "Use [clarify] and [policy] here", "", "", "")
    out = console.export_text()
    assert "[clarify]" in out
    assert "[policy]" in out
    assert "System Prompt" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_phase2.py -k "summary_card or bracket_tokens" -v`
Expected: FAIL — `cli.render` does not exist.

- [ ] **Step 3: Create `cli/render.py`**

```python
"""CLI presentation helpers (human-tier output only).

IMPORTANT: machine-output paths (--json-only / --out / --format / --quiet /
batch) must NOT use these helpers — they must emit plain, unstyled payloads so
piping and golden-file tests stay stable.
"""
from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

SECTION_TITLES = {
    "system": "System Prompt",
    "user": "User Prompt",
    "plan": "Plan",
    "expanded": "Expanded Prompt",
}


def get_console() -> Console:
    """Return a Console for human CLI output."""
    return Console()


def render_summary_card(console: Console, ir_json: dict) -> None:
    """Print a compact summary panel from an IR v2 dict (model_dump())."""
    policy = (ir_json.get("metadata") or {}).get("policy_summary") or {}
    rows = [
        ("Persona", str(ir_json.get("persona") or "—")),
        ("Domain", str(ir_json.get("domain") or "—")),
        ("Risk", str(policy.get("risk_level") or "—")),
        ("Output", str(ir_json.get("output_format") or "—")),
        ("Goals", str(len(ir_json.get("goals") or []))),
        ("Constraints", str(len(ir_json.get("constraints") or []))),
    ]
    body = "\n".join(f"{escape(k)}: {escape(v)}" for k, v in rows)
    console.print(Panel(body, title="Summary", expand=False))


def render_prompt_sections(
    console: Console, system: str, user: str, plan: str, expanded: str
) -> None:
    """Print each non-empty prompt section under a rule, markup-safe."""
    sections = [
        (SECTION_TITLES["system"], system),
        (SECTION_TITLES["user"], user),
        (SECTION_TITLES["plan"], plan),
        (SECTION_TITLES["expanded"], expanded),
    ]
    for title, text in sections:
        if text:
            console.rule(title)
            console.print(text, markup=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli_phase2.py -k "summary_card or bracket_tokens" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/render.py tests/test_cli_phase2.py
git commit -m "feat(cli): add cli/render.py human-tier rendering helpers"
```

---

## Task 3: Human-first `compile` default (and fix `--quiet`)

**Files:**
- Modify: `cli/commands/core.py` (`_run_compile`, lines ~197-315)
- Test: `tests/test_cli_phase2.py`

Context: In `_run_compile`, the v2 emitter strings are gated on `(ir2 and render_v2)` (lines 197-213). With the default (`render_v2=False`) they are all `""`, so `--quiet` prints a blank line and the default path dumps only raw IR JSON (`print(rendered)`, line ~310). We (a) compute v2 emitters whenever `ir2` exists — which also makes `--quiet` honest — and (b) replace the default human block with the summary card + sections.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_phase2.py`:

```python
import json as _json

from typer.testing import CliRunner

from cli.main import app as _app

_runner = CliRunner()


def test_compile_default_shows_rendered_sections_not_raw_ir():
    result = _runner.invoke(_app, ["compile", "write a haiku about the sea"])
    assert result.exit_code == 0
    assert "System Prompt" in result.stdout
    assert "User Prompt" in result.stdout
    # Default no longer dumps the raw IR JSON object
    assert '"version": "2.0"' not in result.stdout


def test_compile_json_only_still_outputs_valid_json():
    result = _runner.invoke(_app, ["compile", "write a haiku", "--json-only"])
    assert result.exit_code == 0
    parsed = _json.loads(result.stdout)
    assert parsed.get("version") == "2.0"


def test_compile_quiet_emits_nonempty_system_prompt():
    result = _runner.invoke(_app, ["compile", "write a haiku", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_phase2.py -k "compile_default or quiet_emits" -v`
Expected: FAIL — default shows raw IR (no "System Prompt"); `--quiet` stdout is empty. (`json_only` test may already pass.)

- [ ] **Step 3: Compute v2 emitters unconditionally**

In `cli/commands/core.py`, in `_run_compile`, replace the gated emitter block (lines 197-213) so the `and render_v2` conditions become "whenever ir2 exists":

```python
    # Resolve quiet vs json_only
    if json_only and quiet:
        quiet = False
    system_prompt = (
        emit_system_prompt(ir) if ir else (emit_system_prompt_v2(ir2) if ir2 else "")
    )
    if quiet:
        print(system_prompt)
        return
    user_prompt = emit_user_prompt(ir) if ir else (emit_user_prompt_v2(ir2) if ir2 else "")
    plan = emit_plan(ir) if ir else (emit_plan_v2(ir2) if ir2 else "")
    expanded = (
        emit_expanded_prompt(ir, diagnostics=diagnostics)
        if ir
        else (emit_expanded_prompt_v2(ir2, diagnostics=diagnostics) if ir2 else "")
    )
```

- [ ] **Step 4: Allow `--format md` to include v2 prompts**

Still in `_run_compile`, the `--format md` guards read `(ir or (ir2 and render_v2))` at lines ~232, ~255, ~287. Change each of those three conditions to `(ir or ir2)` so saved/printed Markdown includes the v2 prompts now that they are always computed. (Search the function for `ir2 and render_v2` and replace each occurrence with `ir2`.)

- [ ] **Step 5: Replace the default human-output block with the summary card + sections**

In `_run_compile`, replace the default rendering block (the lines that print Persona/Role or "IR v2", then `print("\n[bold blue]IR JSON:[/bold blue]")`, build `rendered`, and the `if ir or (ir2 and render_v2):` section dump — lines ~275-315, but NOT the `if out or out_dir:` save branch in between) with this. Keep the `if out or out_dir:` save branch intact (it writes files and returns before reaching here).

Add this import near the top of `cli/commands/core.py` with the other `from app...`/`from cli...` imports:

```python
from cli.render import get_console, render_summary_card, render_prompt_sections
```

Then the default console path becomes:

```python
    if ir:
        # Legacy v1 path keeps its existing simple rendering.
        print(f"[bold white]Persona:[/bold white] {ir.persona} (heuristics v{HEURISTIC_VERSION})")
        print(f"[bold white]Role:[/bold white] {ir.role}")
        console = get_console()
        render_prompt_sections(console, system_prompt, user_prompt, plan, expanded)
        return
    # Default v2 path: human-first summary card + rendered prompts.
    console = get_console()
    render_summary_card(console, ir_json)
    render_prompt_sections(console, system_prompt, user_prompt, plan, expanded)
```

Note: the raw `rendered = orjson.dumps(...)` default dump and the `print("\n[bold blue]IR JSON:[/bold blue]")` line are removed from this default path. Raw IR remains available via `--json-only` (unchanged) and the `--out`/`--format` save branches (unchanged).

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_cli_phase2.py -k "compile_default or json_only or quiet_emits" -v`
Expected: PASS.

- [ ] **Step 7: Update existing tests that assumed the old default**

Run the CLI test files to find breakage from the default change:
Run: `python -m pytest tests/ -k "cli or compile" -q`
For every failure where a test invoked `compile` WITHOUT `--json-only` and asserted raw-IR/JSON output, update that test to add `--json-only` (the machine contract is unchanged there) or to assert the new rendered sections. Do NOT change `--json-only`/`--out`/`--quiet` behavior. Re-run until green.

- [ ] **Step 8: Commit**

```bash
git add cli/commands/core.py tests/test_cli_phase2.py
git add -u tests/
git commit -m "feat(cli): human-first compile output by default; fix --quiet"
```

---

## Task 4: Add a metadata header to `pack` output

**Files:**
- Modify: `app/utils.py` (`_render_prompt_pack_md`, `_render_prompt_pack_txt`)
- Modify: `cli/commands/core.py` (`pack_command`, lines ~944-967)
- Test: `tests/test_cli_phase2.py`

Context: `pack_command` already computes `ir2`/`ir`, the four prompt strings, and `ir_ver` (`"v1"`/`"v2"`). The renderers in `app/utils.py` take only the four strings. Add an optional `header` string param so the command can prepend a compact metadata block.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_phase2.py`:

```python
def test_pack_md_includes_metadata_header():
    result = _runner.invoke(_app, ["pack", "build a rest api", "--format", "md"])
    assert result.exit_code == 0
    assert "Domain:" in result.stdout
    assert "IR version:" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_phase2.py::test_pack_md_includes_metadata_header -v`
Expected: FAIL — no header in pack output.

- [ ] **Step 3: Add an optional `header` param to the renderers in `app/utils.py`**

Replace the two functions with:

```python
def _render_prompt_pack_md(
    system_prompt: str,
    user_prompt: str,
    plan: str,
    expanded: str,
    title: str = "Prompt Pack",
    header: str = "",
) -> str:
    """Render a prompt pack in Markdown format."""
    parts = [f"# {title}"]
    if header:
        parts.append(f"\n\n{header}")
    if system_prompt:
        parts.append(f"\n\n## System Prompt\n\n{system_prompt}")
    if user_prompt:
        parts.append(f"\n\n## User Prompt\n\n{user_prompt}")
    if plan:
        parts.append(f"\n\n## Plan\n\n{plan}")
    if expanded:
        parts.append(f"\n\n## Expanded Prompt\n\n{expanded}")
    return "".join(parts).strip()


def _render_prompt_pack_txt(
    system_prompt: str,
    user_prompt: str,
    plan: str,
    expanded: str,
    header: str = "",
) -> str:
    """Render a prompt pack in Plain Text format."""
    parts = []
    if header:
        parts.append(f"{header}\n")
    if system_prompt:
        parts.append(f"--- System Prompt ---\n{system_prompt}")
    if user_prompt:
        parts.append(f"\n\n--- User Prompt ---\n{user_prompt}")
    if plan:
        parts.append(f"\n\n--- Plan ---\n{plan}")
    if expanded:
        parts.append(f"\n\n--- Expanded Prompt ---\n{expanded}")
    return "".join(parts).strip()
```

- [ ] **Step 4: Build and pass the header in `pack_command`**

In `cli/commands/core.py`, inside `pack_command`, just before the `fmt_l = (format or "md").lower()` line (line ~961), add:

```python
    if v1:
        _domain = "—"
        _persona = getattr(ir, "persona", "—")
        _risk = "—"
    else:
        _ir2_json = ir2.model_dump()
        _domain = _ir2_json.get("domain") or "—"
        _persona = _ir2_json.get("persona") or "—"
        _risk = ((_ir2_json.get("metadata") or {}).get("policy_summary") or {}).get(
            "risk_level"
        ) or "—"
    pack_header = (
        f"Domain: {_domain} | Persona: {_persona} | Risk: {_risk} | IR version: {ir_ver}"
    )
```

Then update the md and txt calls (lines ~963 and ~966) to pass the header:

```python
        payload = _render_prompt_pack_md(
            system_prompt, user_prompt, plan, expanded, header=pack_header
        )
```
```python
        payload = _render_prompt_pack_txt(
            system_prompt, user_prompt, plan, expanded, header=pack_header
        )
```

(The `json` format branch is left unchanged — it already carries `ir_version`/`heuristic_version`.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_cli_phase2.py::test_pack_md_includes_metadata_header -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/utils.py cli/commands/core.py tests/test_cli_phase2.py
git commit -m "feat(cli): add metadata header to pack output"
```

---

## Task 5: Full verification + draft PR

- [ ] **Step 1: ruff + full suite**

Run: `python -m ruff check cli/ app/ tests/test_cli_phase2.py`
Run: `python -m pytest tests/ -q`
Expected: ruff clean; suite green (with any Task 3 Step 7 test updates applied).

- [ ] **Step 2: Clean-venv smoke test (real published behavior)**

```bash
SCRATCH="/private/tmp/claude-501/-Users-mehmetozel-Developer-personal-Compiler/23364b9e-b080-4fdf-bcd9-67c530a7cb8f/scratchpad"
rm -rf "$SCRATCH/dist2" "$SCRATCH/smoke-venv2"
python -m build --wheel --outdir "$SCRATCH/dist2"
python -m venv "$SCRATCH/smoke-venv2"
"$SCRATCH/smoke-venv2/bin/pip" install -q "$SCRATCH"/dist2/prcompiler-*.whl
"$SCRATCH/smoke-venv2/bin/promptc" compile "write a haiku about the sea"
```
Expected: output shows a Summary panel + System/User/Plan/Expanded sections, NO leading `[STRATEGIST]` line, NO raw IR JSON dump.

- [ ] **Step 3: Push and open a DRAFT PR**

```bash
git push -u origin feat/cli-phase2-output-ux
gh pr create --draft --base main --head feat/cli-phase2-output-ux \
  --title "CLI Phase 2: compile/pack output & UX" \
  --body "Human-first compile output (summary card + rendered prompts by default; raw IR via --json-only), new cli/render.py, pack metadata header, fixed --quiet, and silenced the [STRATEGIST] stderr noise. Emitters/heuristics untouched; machine paths stay plain. Spec: docs/superpowers/specs/2026-06-24-cli-phase2-output-ux-design.md"
```

- [ ] **Step 4: Report** changed files, smoke-test output, CI status. Do NOT merge without explicit user approval.

---

## Self-Review (completed by author)

- **Spec coverage:** (A) `cli/render.py` → Task 2. (B) compile human-first + `--quiet` → Task 3. (C) pack header → Task 4. (D) `[STRATEGIST]` noise → Task 1. Machine paths stay plain (Task 3 keeps `--json-only`/`--out`/`--quiet` branches). All covered. Spec's optional `.txt` "### Context" cleanup is intentionally dropped: on inspection that bleed comes from emitter *content* (out of scope — emitters untouched), not from `_render_prompt_pack_txt`, which already uses `--- X ---` delimiters.
- **Placeholder scan:** none — every code step shows concrete content. Task 3 Step 7 is a discovery-and-fix step with an exact command and explicit criteria, not a placeholder.
- **Type/name consistency:** `get_console`, `render_summary_card(console, ir_json)`, `render_prompt_sections(console, system, user, plan, expanded)`, `SECTION_TITLES`, `pack_header`, `header=` param are used identically across Tasks 2-4. Summary card reads `metadata.policy_summary.risk_level` — verified against a real `compile --json-only` dump.
- **Risk:** Task 3 changes the flagship default; Step 7 explicitly updates tests that relied on the old default. Reversible.
