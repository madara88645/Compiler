# CLI Phase 1 — Vitrin & Kurulum (Public Face & Installability)

**Date:** 2026-06-24
**Scope:** `cli/` + `README.md` only. No changes to `app/`, `api/`, or `web/`.
**Status:** Approved design (hard-delete confirmed) → ready for implementation plan.

## Özet (TR)
PyPI'a `prcompiler` adıyla yayınlamadan önce CLI'nin "ilk izlenim" sorunlarını gideriyoruz:
(A) `--help`'i kirleten 4 boş "DEPRECATED" komutunu siliyoruz, (B) paketin temiz bir venv'e
kurulup `promptc compile` çalıştığını doğrulayıp README'ye kurulum bölümü ekliyoruz,
(C) konvansiyonel `--version` flag'i ve davetkâr bir top-level help ekliyoruz. Sadece `cli/`
ve `README.md`. Risk düşük.

## Context / Problem
The project is about to publish its CLI to PyPI under the new distribution name
`prcompiler` (the `promptc` name on PyPI is held by an unrelated package; rename merged in #843).
The first `pip install prcompiler` impression matters for an HN/PH-style launch. Current issues:

1. **Deprecated clutter** — `promptc --help` lists four command groups that are pure stubs:
   `favorites`, `snippets`, `collections`, `palette`. Each only prints
   "X feature has been deprecated and removed." They are defined in `cli/commands/resources.py`
   and mounted in `cli/main.py`. They confuse new users and look unmaintained.
2. **Installability unverified** — in the dev venv the `promptc` console script is not installed
   (`command not found`); the CLI runs via `python -m cli.main`. Templates load via
   `importlib.resources` (`app/templates.py:132`) and schemas ship as package-data, so an
   installed package *should* work, but this has not been smoke-tested against a clean install.
3. **No `--version` flag** — version is only a subcommand (`promptc version`); the conventional
   `--version` eager flag is missing. Top-level help is the bland
   "Core compiler and utility commands".

## Goals
- `promptc --help` shows only real, working commands (no DEPRECATED entries).
- A clean `pip install` / `pipx install prcompiler` yields a working `promptc` command,
  verified end-to-end with a smoke test.
- Conventional `promptc --version` works; top-level help is inviting and shows a usage example.
- README has a short, correct install section.

## Non-Goals (explicit — deferred to later phases)
- Output / UX redesign of `compile`/`pack` (Phase 2).
- Splitting the 1133-line `cli/commands/core.py` (Phase 3).
- Bringing web-only features (e.g. PR Safety) into the CLI (Phase 4).
- Any change under `app/`, `api/`, `web/`, provider/deploy/CI config.

## Design

### A) Remove deprecated commands (hard-delete — approved)
Rationale for hard-delete over a soft one-release deprecation: `prcompiler` is a brand-new PyPI
name with **zero existing pip users** to break, and the four groups are already gutted stubs with
no functionality. A soft path would add cruft to a tool we are trying to declutter.

- `cli/main.py`: remove the `from cli.commands.resources import (...)` block and the four
  `app.add_typer(..., name="favorites|snippets|collections|palette")` mounts.
- Delete `cli/commands/resources.py` (only importer is `cli/main.py`, confirmed by grep).
- `tests/test_favorites.py`: delete (it covers the removed stub) — or, if it also asserts
  unrelated behavior, trim to drop only the favorites-command assertions. Implementation step
  must read the file first and decide.

### B) Verify installability + document
- Build a wheel and `pip install` it into a fresh, isolated virtualenv (not editable).
- Smoke-test: `promptc --help` exits 0 and lists commands; `promptc compile "write a haiku"`
  runs and produces output (no missing-data-file crash). This exercises the
  `importlib.resources` template path and the `_schemas` package-data.
- If anything fails to resolve, the only expected fix is extending
  `[tool.setuptools.package-data]` in `pyproject.toml` (no app code change).
- README: add an "Install" section — `pipx install prcompiler` (recommended) or
  `pip install prcompiler`, followed by a one-line `promptc compile "..."` example.

### C) `--help` / `--version` polish
- Add a top-level eager `--version` callback to the root Typer app that prints the package
  version (read via `importlib.metadata.version("prcompiler")`, with a safe fallback) and exits.
  Keep the existing `version` subcommand for back-compat.
- Replace the root help string "Core compiler and utility commands" with an inviting one-liner
  plus a short usage example in the app's help/epilog.

## Files Affected
- `cli/main.py` — remove deprecated imports + mounts; wire `--version` callback.
- `cli/commands/resources.py` — deleted.
- `cli/commands/core.py` — root Typer help text; `--version` may live here or in `main.py`.
- `tests/test_favorites.py` — removed/trimmed.
- `README.md` — Install section.
- `pyproject.toml` — only if the smoke test reveals missing package-data.

## Testing & Verification
- Existing pytest suite must stay green (CI runs full suite).
- New/updated: a test asserting `promptc --help` output contains none of
  `favorites|snippets|collections|palette`, and that `--version` prints the version.
- Manual/CI smoke test: clean-venv install + `promptc compile` run (documented in the PR).

## Risks
- **Low.** CLI-surface only. No `app/api/web`, provider, deploy, DB, or dependency changes.
  Hard-delete is safe because the targets are isolated stubs. The one residual unknown —
  whether an installed (non-editable) package resolves all data files — is closed by the
  Phase B smoke test before merge.

## Rollout
- Single focused PR ("CLI Phase 1: vitrin & kurulum"), draft until smoke test passes.
- Sequencing decision: cut the `v2.0.46` PyPI release **after** this PR merges, so the first
  published `prcompiler` version is the cleaned-up one. PyPI trusted-publisher registration can
  be done independently at any time.
