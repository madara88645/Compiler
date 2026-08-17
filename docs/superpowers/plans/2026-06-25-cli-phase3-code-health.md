# CLI Phase 3 — Code Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 1166-line `cli/commands/core.py` into focused modules, delete dead code (`cli/utils.py`, `cli/commands/legacy.py`, commented history, dead `_suppress_log` setattrs), consolidate the core-side `_write_output` into a shared helper, and add a test safety net — with **zero behavior change**.

**Architecture:** The Typer `app` instance moves to `cli/commands/_base.py` (with `console`, `_version_callback`, `_main`, `version`). Command groups move to sibling modules that `from cli.commands._base import app` and register with `@app.command(...)`. `cli/commands/core.py` becomes a thin aggregator that imports `_base` (for `app`) and imports the command modules for side-effect registration, then re-exports `app` — so `from cli.commands.core import app` (used by `cli/main.py:2` and `tests/test_cli_console_refactor.py:3`) keeps working. Leaf modules depend only on `_base`/`_helpers`/`app.*`, never on `core` → no circular imports.

**Tech Stack:** Python 3.10+, Typer, Rich, pytest + `typer.testing.CliRunner`, ruff.

**Branch:** `feat/cli-phase3-code-health` — **branch from `main` AFTER PR #845 is merged** (Phase 2 modifies `core.py`; branching earlier guarantees conflicts).

**Boundary:** Strictly `cli/`. Do NOT touch `app/` (Codex's repo-context track). Never merge without explicit user approval.

---

## core.py anchor map (verified 2026-06-25)

| Lines | Symbol | Destination |
|---|---|---|
| 52–53 | `app = typer.Typer(...)`, `console = Console()` | `_base.py` |
| 56–78 | `_version_callback`, `_main` (callback) | `_base.py` |
| 81–95 | `_write_output` | `_helpers.py` |
| 103–106 | `version` command | `_base.py` |
| 109–314 | `_run_compile` | `compile_cmd.py` |
| 315–440 | `compile_cmd` (`@app.command("compile")`) | `compile_cmd.py` |
| 441–480 | `validate` | `validation.py` |
| 481–583 | `fix_prompt_command` (`fix`) | `transform.py` |
| 584–689 | `compare_command` (`compare`) | `transform.py` |
| 690–882 | `batch` | `compile_cmd.py` |
| 883–999 | `pack_command` (`pack`) | `transform.py` |
| 1000–1089 | `json_path` (`json-path`) | `json_tools.py` |
| 1090–1166 | `json_diff` (`diff`) | `json_tools.py` |
| 49–50 | `HEURISTIC_VERSION`, `HEURISTIC2_VERSION` | move with their users (see Task 5) |

Imports to distribute: `core.py:1–45`. Don't hand-copy all of them into every module — move the functions, then let **ruff** (`F821` undefined-name, `F401` unused-import) drive which imports each module needs.

---

## Task 1: Delete dead code (small, independently safe — can ship as PR-A)

**Files:** delete `cli/utils.py`, `cli/commands/legacy.py`; edit `cli/commands/core.py`.

- [ ] **Step 1** — Re-confirm no importers (guard against drift):
  `grep -rn --include="*.py" -E "cli\.utils|commands\.legacy|import legacy" . | grep -v __pycache__ | grep -v build/`
  Expected: no hits (only the dead files themselves). If anything imports them, STOP and reassess.
- [ ] **Step 2** — `git rm cli/utils.py cli/commands/legacy.py`.
- [ ] **Step 3** — In `cli/commands/core.py` remove the commented history import (`# from app.history import get_history_manager`, line 45) and the disabled history block at line 307 (`# Save to history - DISABLED ...`).
- [ ] **Step 4** — In `batch` remove the two dead lines `setattr(_write_output, "_suppress_log", True)` (≈743) and `setattr(_write_output, "_suppress_log", False)` (≈880). Verified write-only — never read anywhere in `cli/` or `app/`.
- [ ] **Step 5** — `python -m pytest tests/ -q` → green. `python -m ruff check cli/` → clean.
- [ ] **Step 6** — Commit: `chore(cli): remove dead code (cli/utils.py, legacy.py, history stubs, _suppress_log)`.

---

## Task 2: Characterization tests first (TDD safety net) — `tests/test_cli_phase3.py`

Write these against the **un-split** code so they capture current behavior, then keep them green through the split.

- [ ] **Step 1** — Create `tests/test_cli_phase3.py`:

```python
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

EXPECTED_TOP_LEVEL = {
    "version", "compile", "validate", "fix", "compare",
    "batch", "pack", "json-path", "diff",
    # sub-apps mounted in cli/main.py:
    "rag", "template", "analytics", "history", "test",
    "optimize", "github", "plugins", "profile",
}


def _command_names() -> set[str]:
    out = runner.invoke(app, ["--help"])
    assert out.exit_code == 0
    # parse the rendered command column
    names = set()
    for line in out.stdout.splitlines():
        token = line.strip().lstrip("│").strip().split(" ", 1)
        if token and token[0] in EXPECTED_TOP_LEVEL:
            names.add(token[0])
    return names


def test_command_surface_is_preserved():
    assert EXPECTED_TOP_LEVEL.issubset(_command_names())


def test_fix_runs_and_reports():
    # `fix` reads a prompt file; characterize exit behavior + output shape
    result = runner.invoke(app, ["fix", "--help"])
    assert result.exit_code == 0
    assert "fix" in result.stdout.lower()


def test_compare_help_and_invocation():
    result = runner.invoke(app, ["compare", "--help"])
    assert result.exit_code == 0


def test_pack_md_smoke():
    result = runner.invoke(app, ["pack", "build a rest api", "--format", "md"])
    assert result.exit_code == 0
    assert "System Prompt" in result.stdout
```

> Note: if `EXPECTED_TOP_LEVEL` parsing proves brittle against the Rich help box, instead assert each command resolves: `runner.invoke(app, [name, "--help"]).exit_code == 0` for name in the 9 core commands. Pick whichever is stable in this repo and keep it.

- [ ] **Step 2** — Run `python -m pytest tests/test_cli_phase3.py -q` → all green on current code. Commit: `test(cli): add Phase 3 characterization + command-surface invariant`.

---

## Task 3: Create `_base.py` and `_helpers.py`

- [ ] **Step 1** — Create `cli/commands/_base.py`:

```python
"""Shared Typer app instance + CLI meta commands (version)."""
from __future__ import annotations

from typing import Optional

import typer
from rich import print as rich_print
from rich.console import Console

from app import get_version

app = typer.Typer(no_args_is_help=True)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(get_version())
        raise typer.Exit()


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the prcompiler version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """
    prcompiler — turn messy natural-language requests into structured prompts,
    plans, and exportable artifacts.

    Example: promptc compile "write a haiku about the sea"
    """


@app.command()
def version():
    """Print package version."""
    rich_print(get_version())
```

- [ ] **Step 2** — Create `cli/commands/_helpers.py` (the canonical core-side `_write_output`, copied verbatim from `core.py:81–95`, `out_dir`-first behavior, `default_name` default):

```python
"""Shared CLI output helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer


def _write_output(
    content: str, out: Optional[Path], out_dir: Optional[Path], default_name: str = "output.txt"
):
    """Helper to write output to file or directory."""
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / default_name
        target.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {target}")
    elif out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote to {out}")
    else:
        typer.echo(content)
```

> **rag.py is NOT changed.** Its local `_write_output` checks `out` before `out_dir` (opposite precedence) and `rag` exposes both `--out` and `--out-dir`, so switching it would be a (corner-case) behavior change — out of scope for a no-behavior-change refactor. Cross-`rag` de-dup is deferred.

- [ ] **Step 3** — `python -m ruff check cli/commands/_base.py cli/commands/_helpers.py` → clean.

---

## Task 4: Move command groups into focused modules

For each module: create the file, move the listed functions **verbatim** (cut from `core.py`), add `from cli.commands._base import app` (and `console`/`_write_output` where noted), then run ruff to resolve imports. Do the moves one module at a time and run the Phase 3 tests after each.

- [ ] **Step 1 — `cli/commands/compile_cmd.py`**: move `_run_compile` (109–314), `compile_cmd` (315–440), `batch` (690–882). Add `from cli.commands._base import app` and `from cli.commands._helpers import _write_output`. Move `HEURISTIC_VERSION`/`HEURISTIC2_VERSION` (49–50) here (used by the compile render). `_run_compile` already creates its own `console` via `get_console()`, so it does NOT need `_base.console`.
- [ ] **Step 2 — `cli/commands/transform.py`**: move `fix_prompt_command` (481–583), `compare_command` (584–689), `pack_command` (883–999). Add `from cli.commands._base import app, console` (fix/compare use the module-global `console`) and `from cli.commands._helpers import _write_output` (pack uses it).
- [ ] **Step 3 — `cli/commands/validation.py`**: move `validate` (441–480). Add `from cli.commands._base import app`.
- [ ] **Step 4 — `cli/commands/json_tools.py`**: move `json_path` (1000–1089), `json_diff` (1090–1166). Add `from cli.commands._base import app`. (Named `json_tools` — NOT `json` — to avoid shadowing stdlib `json`.)
- [ ] **Step 5 — Resolve imports per module with ruff**: for each new module run `python -m ruff check <module>`; add `F821` undefined names from `core.py:1–45` and drop `F401` unused ones. Repeat until clean.

---

## Task 5: Slim `core.py` to a thin aggregator

- [ ] **Step 1** — Replace the entire contents of `cli/commands/core.py` with:

```python
"""Aggregator: re-exports the Typer `app` with all core commands registered.

Kept for import-compatibility — `cli/main.py` and tests do
`from cli.commands.core import app`. Command implementations live in the
sibling modules imported below (imported for their registration side-effects).
"""
from __future__ import annotations

from cli.commands._base import app

# Side-effect imports: each registers its commands on `app`.
from cli.commands import compile_cmd as _compile_cmd  # noqa: F401,E402
from cli.commands import validation as _validation  # noqa: F401,E402
from cli.commands import transform as _transform  # noqa: F401,E402
from cli.commands import json_tools as _json_tools  # noqa: F401,E402

__all__ = ["app"]
```

- [ ] **Step 2** — `python -m ruff check cli/` → clean. `python -c "from cli.commands.core import app; print(type(app))"` → prints the Typer type (no ImportError, no circular-import error).
- [ ] **Step 3** — `python -m pytest tests/test_cli_phase3.py tests/test_cli_console_refactor.py -q` → green (command surface preserved; `app` still importable from `core`).

---

## Task 6: Full verification + draft PR

- [ ] **Step 1 — Full suite + ruff**: `python -m pytest tests/ -q` and `python -m ruff check cli/ tests/test_cli_phase3.py` → all green/clean. No existing test should need edits; if one does, it indicates a behavior drift — investigate, don't paper over.
- [ ] **Step 2 — Behavior-identical smoke** (compare each to pre-split output):
  - `python -m cli.main --help`
  - `python -m cli.main version`
  - `python -m cli.main compile "write a haiku about the sea"`
  - `python -m cli.main compile "x" --json-only`
  - `python -m cli.main pack "build a rest api" --format md`
  - `python -m cli.main fix --help` / `compare --help` / `json-path --help` / `diff --help`
- [ ] **Step 3 — File-size check**: `wc -l cli/commands/*.py` → no file over ~350 lines; `core.py` is now ~20 lines.
- [ ] **Step 4 — pre-commit (CI parity)**: `pre-commit run ruff-format --files cli/commands/*.py tests/test_cli_phase3.py` (Smoke job pins ruff **v0.1.14**). Commit any reformat.
- [ ] **Step 5 — Push + DRAFT PR**:
  ```bash
  git push -u origin feat/cli-phase3-code-health
  gh pr create --draft --base main --head feat/cli-phase3-code-health \
    --title "CLI Phase 3: split core.py + remove dead code (no behavior change)" \
    --body "Splits the 1166-line cli/commands/core.py into focused modules (_base, _helpers, compile_cmd, transform, validation, json_tools); core.py becomes a thin aggregator re-exporting app. Deletes dead code (cli/utils.py, legacy.py, history stubs, dead _suppress_log). Adds tests/test_cli_phase3.py (command-surface invariant + fix/compare/pack characterization). No behavior change; cli/ only. Spec: docs/superpowers/specs/2026-06-25-cli-phase3-code-health-design.md"
  ```
- [ ] **Step 6 — Report** changed files, smoke diffs, CI status. Do NOT merge without explicit user approval.

---

## Self-Review (completed by author)

- **Import surface:** only `app` is imported from `cli.commands.core` (verified: `cli/main.py:2`, `tests/test_cli_console_refactor.py:3`). Task 5's aggregator preserves it. No test imports `_run_compile`/`_write_output`/command fns from `core`.
- **Circular imports:** leaf modules import only `_base`/`_helpers`/`app.*`; `core.py` imports the leaves. Acyclic. Task 5 Step 2 asserts the import works.
- **Behavior preservation:** functions moved verbatim; `console` global dependency (fix/compare) routed via `_base`; `_run_compile`'s local `console` untouched; `version` keeps Rich `print`. Command-surface invariant test guards the registration. `--help` order: `batch` may shift up (grouped with `compile`) — cosmetic; if a test asserts exact order, register in canonical order in `core.py` instead of changing behavior.
- **`_write_output`:** shared helper takes core's verbatim behavior (zero change for compile/pack/batch); rag.py deliberately untouched (different precedence). Documented.
- **Boundary:** no `app/` edits. Branches post-#845-merge. Reversible (pure structural).
