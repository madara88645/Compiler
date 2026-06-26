# CLI Phase 3 — Code Health (split `core.py`, remove dead code)

**Date:** 2026-06-25
**Scope:** `cli/` only. Split the monolithic `cli/commands/core.py` into focused modules, delete dead files, de-duplicate one helper, add tests for currently-untested commands. **No behavior change.**
**Status:** Approved roadmap → design (this doc) → implementation plan → execution.
**Predecessor:** Phase 2 (compile/pack output & UX) — **must be merged first** (PR #845 touches `core.py`; Phase 3 branches from updated `main` to avoid conflicts).
**Boundary:** Strictly `cli/`. A parallel worker (Codex) owns `app/` repo-context work — no shared files.

## Özet (TR)
`cli/commands/core.py` 1166 satırlık tek dev dosya: 9 komut + 197 satırlık `_run_compile`
helper'ı bir arada. Faz 3 bunu **odaklı küçük modüllere** böler, ölü kodu siler
(`cli/utils.py` 215 satırlık kullanılmayan duplikat, `cli/commands/legacy.py` boş stub,
`core.py` içindeki yorum-history kodu, hiç okunmayan `_suppress_log` setattr'ları) ve
core tarafındaki `_write_output` helper'ını ortak `_helpers.py`'ye taşır (`rag.py`'ninki
önceliği farklı olduğu için dokunulmadan bırakılır).
**Kullanıcı için hiçbir şey değişmez** — komut isimleri, flag'ler, çıktı aynı. Test
güvenlik ağı: mevcut CLI testlerinin tamamı değişmeden geçmeli + komut listesi birebir
korunmalı. Ek olarak test edilmeyen `fix`/`compare`/`pack` komutlarına temel test eklenir.

## Context / Problem (verified against source)
- `cli/commands/core.py` is **1166 lines** holding 9 top-level commands plus a 197-line
  `_run_compile` helper (`core.py:109`). Hard to navigate; high merge-conflict surface.
- **Only `app` is imported from `core`** — verified: `cli/main.py:2`
  (`from cli.commands.core import app as core_app`) and
  `tests/test_cli_console_refactor.py:3` (`from cli.commands.core import app`). No code
  imports `_run_compile`, `compile_cmd`, `_write_output`, etc. from `core`. → splitting is
  low-risk as long as `from cli.commands.core import app` keeps resolving.
- **Dead code (verified):**
  - `cli/utils.py` (215 lines) — a stale duplicate of `_run_compile`/`_write_output`;
    grep confirms **no importer** anywhere.
  - `cli/commands/legacy.py` (13 lines) — a placeholder stub (`app = typer.Typer(help="Legacy/Extras")`)
    + a comment wall; **not imported** anywhere; not mounted in `main.py`.
  - `core.py` commented-out history integration: `# from app.history import get_history_manager`
    (`core.py:45`) and the disabled block at `core.py:307`.
  - `_suppress_log`: set via `setattr(_write_output, "_suppress_log", True/False)` in `batch`
    (`core.py:743`, `core.py:880`) but **never read** anywhere → vestigial.
- **`_write_output` duplication:** defined in `cli/commands/core.py:81` and
  `cli/commands/rag.py:20` (and the dead `cli/utils.py:35`). Once the dead `_suppress_log`
  setattrs are removed, the `core.py` and `rag.py` copies are functionally identical.
- **Test gaps:** `fix`, `compare`, `pack` commands have no dedicated CLI tests
  (only incidental coverage). Refactoring them blind is risky → add characterization tests first.

## Goals
- `cli/commands/core.py` shrinks to a thin aggregator; each command group lives in its own
  small module (target: no CLI file over ~350 lines).
- `from cli.commands.core import app` and `from cli.main import app` continue to work
  unchanged; the full top-level command set is **byte-for-byte preserved**.
- One shared `_write_output`; dead files/code removed.
- `fix` / `compare` / `pack` gain characterization tests (added **before** they are moved).
- Zero behavior change: every existing test passes unchanged (except trivial import-path
  updates if a test imported an internal symbol — none currently do).

## Non-Goals (explicit)
- **No `app/` edits** (compiler, emitters, heuristics, pr_safety, repo-context) — that surface
  belongs to the parallel Codex track.
- No new commands, flags, or output format changes. No new features (PR Safety in CLI = Phase 4).
- No change to the sub-apps (`rag`, `analytics`, `optimize`, etc.) beyond the shared
  `_write_output` import in `rag.py`. They are already separate modules.
- No dependency, packaging, or CI config changes.

## Design

### Target module layout (`cli/commands/`)
| New module | Owns | From `core.py` lines |
|---|---|---|
| `_base.py` | `app = typer.Typer(no_args_is_help=True)`, module `console`, `_version_callback`, `_main` callback, `version` command | 52–106 |
| `_helpers.py` | shared `_write_output` (used by compile group **and** `rag.py`) | 81–95 |
| `compile_cmd.py` | `_run_compile`, `compile`, `batch` | 109–438, 690–880 |
| `transform.py` | `fix`, `compare`, `pack` | 481–687, 883–997 |
| `validation.py` | `validate` | 441–478 |
| `json_tools.py` | `json-path`, `diff` (NOT `json.py` — would shadow stdlib `json`) | 1000–1166 |
| `core.py` (slimmed) | `from cli.commands._base import app`; import the command modules for side-effect registration; **re-export `app`** | — |

### Registration / circular-import strategy
The Typer `app` instance lives in **`_base.py`**. Each command module does
`from cli.commands._base import app` and registers its commands with `@app.command()`.
`core.py` imports `_base` (for `app`) and then imports `compile_cmd`, `transform`,
`validation`, `json_tools` purely for their registration side-effects, then exposes `app`.
Leaf modules depend only on `_base`/`_helpers`/`app.*` — never on `core` — so there is **no
circular import**. `_run_compile` stays in `compile_cmd.py` and is shared by `compile` + `batch`
within the same module.

### Command order
Grouping `compile`+`batch` together moves `batch` up in the `--help` listing (cosmetic only;
names/behavior unchanged). This is acceptable. If any test asserts exact command order, the
plan normalizes it (register commands in canonical order in `core.py`) rather than changing it.

### `_write_output` de-duplication (core-side only)
Move the core-side `_write_output` to `cli/commands/_helpers.py`; `compile_cmd.py` imports it
(zero change — `compile`/`pack`/`batch` already use this exact behavior). Drop the two dead
`setattr(_write_output, "_suppress_log", ...)` lines in `batch` (never read).
**`rag.py` is left untouched:** its local `_write_output` checks `out` before `out_dir` (opposite
precedence) and `rag` exposes both `--out` and `--out-dir`, so sharing it would be a corner-case
behavior change. Cross-`rag` de-dup is deferred (out of scope for a no-behavior-change phase).

## Files Affected
- **Create:** `cli/commands/_base.py`, `cli/commands/_helpers.py`, `cli/commands/compile_cmd.py`,
  `cli/commands/transform.py`, `cli/commands/validation.py`, `cli/commands/json_tools.py`.
- **Slim:** `cli/commands/core.py` (→ thin aggregator re-exporting `app`).
- **Delete:** `cli/utils.py`, `cli/commands/legacy.py`.
- **Unchanged:** `cli/commands/rag.py` (keeps its own `_write_output` — see de-dup note above).
- **Tests:** new `tests/test_cli_phase3.py` (command-surface invariant + fix/compare/pack
  characterization). `cli/main.py` and existing tests should need **no** changes.

## Testing & Verification
- **Characterization first (TDD):** before moving anything, add `tests/test_cli_phase3.py`
  asserting current behavior of `fix`, `compare`, `pack` via `CliRunner`, plus a
  **command-surface invariant**: the set of top-level command names equals the known 9
  (`version, compile, validate, fix, compare, batch, pack, json-path, diff`). Run — green on
  the un-split code.
- Perform the split; re-run `python -m pytest tests/test_cli*.py -q` → all green, no test edits.
- Full suite: `python -m pytest tests/ -q`.
- Smoke (output identical to pre-split): `python -m cli.main --help`,
  `python -m cli.main compile "write a haiku about the sea"`,
  `... compile "x" --json-only`, `... pack "build a rest api" --format md`.
- `python -m cli.main version` prints the version (registration intact).
- **CI gotcha:** Smoke job runs pre-commit with ruff **v0.1.14** (not local 0.15.17) — run
  `pre-commit run ruff-format` on changed files before pushing.

## Risks
- **Low.** Pure structural refactor inside `cli/`, behavior preserved, only `app` crosses the
  module boundary (and stays importable from `core`). Main hazards: (a) circular imports —
  mitigated by the `_base.py` instance pattern; (b) Typer registration order — covered by the
  command-surface invariant test; (c) the `_write_output`/`_suppress_log` subtlety — resolved
  (write-only, safe to drop). Fully reversible; `prcompiler` is a new PyPI name with no
  install base depending on internal module paths.

## Rollout (small & reversible)
- **PR-A (optional, tiny):** delete dead code only — `cli/utils.py`, `cli/commands/legacy.py`,
  the `core.py` history comments, the dead `_suppress_log` setattrs. Ships first, trivially safe.
- **PR-B:** the `core.py` split + `_write_output` de-dup + `tests/test_cli_phase3.py`.
- Both draft until CI green + the smoke commands above show identical output to pre-split.
- Branches from `main` **after PR #845 is merged**. Never merge without explicit user approval.
