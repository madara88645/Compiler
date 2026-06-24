# CLI Phase 1 — Vitrin & Kurulum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first `pip install prcompiler` experience clean: drop the four deprecated stub commands, add a working `--version` flag with inviting help, fix the version lookup the rename broke, and verify a clean install end-to-end.

**Architecture:** Surgical edits to the CLI composition root (`cli/commands/core.py`, `cli/main.py`), one one-line bugfix in `app/__init__.py` left over from the `prcompiler` rename (#843), a README install section, and a clean-venv smoke test as the merge gate. No behavior change to any compiler/heuristics/export code.

**Tech Stack:** Python 3.10+, Typer (CLI), Rich (output), pytest + `typer.testing.CliRunner`, setuptools/`build` (packaging).

**Branch:** `feat/cli-phase1-vitrin-kurulum` (already created; spec committed at `75cf919f`).

**⚠️ Spec deviation to confirm with user:** the spec scoped changes to `cli/` + `README.md` only. Task 3 also edits **`app/__init__.py`** (one line) because the `prcompiler` rename left `version("promptc")` there, which makes an installed package report `0.0.0-dev`. It is essential for `--version` to be correct and is a direct consequence of #843. Included here deliberately.

**Scratchpad (for smoke test):** `/private/tmp/claude-501/-Users-mehmetozel-Developer-personal-Compiler/23364b9e-b080-4fdf-bcd9-67c530a7cb8f/scratchpad`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `cli/main.py` | CLI composition root: imports + mounts subcommand groups | Modify — remove deprecated import block + 4 mounts |
| `cli/commands/resources.py` | Four deprecated stub command groups (print "removed") | **Delete** |
| `cli/commands/core.py` | Root Typer `app`, core commands, existing `version` subcommand | Modify — add `--version` eager flag + inviting root help |
| `app/__init__.py` | Best-effort `__version__` / `get_version()` | Modify — `version("promptc")` → `version("prcompiler")` |
| `README.md` | Project docs; `## Installation` is dev-only today | Modify — add CLI (pip/pipx) install subsection |
| `tests/test_cli_phase1.py` | New tests for help cleanliness + `--version` | **Create** |
| `tests/test_favorites.py` | Tests `app/favorites.py` (FavoritesManager) — UNRELATED to CLI stub | **Leave untouched** |
| `pyproject.toml` | Packaging metadata | Modify ONLY if smoke test finds a missing data file (contingency) |

---

## Task 1: Remove the four deprecated stub commands

**Files:**
- Modify: `cli/main.py` (remove lines importing/mounting the deprecated apps)
- Delete: `cli/commands/resources.py`
- Test: `tests/test_cli_phase1.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_phase1.py`:

```python
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

DEPRECATED = ["favorites", "snippets", "collections", "palette"]


def test_help_lists_no_deprecated_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in DEPRECATED:
        assert name not in result.stdout, f"deprecated command still listed: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_phase1.py::test_help_lists_no_deprecated_commands -v`
Expected: FAIL — the help output currently still contains `favorites`, `snippets`, `collections`, `palette`.

- [ ] **Step 3: Remove the import block from `cli/main.py`**

Delete these lines (currently lines 17–22):

```python
from cli.commands.resources import (
    favorites_app,
    snippets_app,
    collections_app,
    palette_app,
)
```

- [ ] **Step 4: Remove the four mounts from `cli/main.py`**

Delete these lines (currently lines 39–42), keeping the `plugins` (38) and `profile` (43) mounts:

```python
app.add_typer(favorites_app, name="favorites")
app.add_typer(snippets_app, name="snippets")
app.add_typer(collections_app, name="collections")
app.add_typer(palette_app, name="palette")
```

After this edit, the "Mount legacy modules" block in `cli/main.py` should read exactly:

```python
# Mount legacy modules
app.add_typer(plugins_app, name="plugins")
app.add_typer(profiles_app, name="profile")
```

- [ ] **Step 5: Delete the stub module**

Run: `git rm cli/commands/resources.py`
(`grep -rn "commands.resources" cli/ tests/` confirmed `cli/main.py` was the only importer.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_cli_phase1.py::test_help_lists_no_deprecated_commands -v`
Expected: PASS.

- [ ] **Step 7: Sanity-check the CLI still imports and runs**

Run: `python -m cli.main --help`
Expected: exit 0, command list shown, no `favorites/snippets/collections/palette` entries.

- [ ] **Step 8: Commit**

```bash
git add cli/main.py tests/test_cli_phase1.py
git rm cli/commands/resources.py
git commit -m "feat(cli): remove deprecated favorites/snippets/collections/palette commands"
```

---

## Task 2: Add a `--version` flag and inviting root help

**Files:**
- Modify: `cli/commands/core.py` (root `app` definition near line 51; `get_version` already imported at line 42, `Optional` at line 10)
- Test: `tests/test_cli_phase1.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_phase1.py`:

```python
from app import get_version


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == get_version()
```

(We compare against `get_version()` rather than a hardcoded number so the test is correct in both editable-dev and installed environments.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_phase1.py::test_version_flag_prints_version -v`
Expected: FAIL — `--version` is not a known option (only the `version` subcommand exists).

- [ ] **Step 3: Implement the `--version` callback and help in `cli/commands/core.py`**

Replace the current line (line 51):

```python
app = typer.Typer(help="Core compiler and utility commands")
```

with:

```python
app = typer.Typer(no_args_is_help=True)
```

Then, immediately after `console = Console()` (currently line 52), insert:

```python
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
```

Notes:
- The callback docstring becomes the root `--help` text (Typer prefers it over the constructor `help=`), so the bland "Core compiler and utility commands" string is intentionally dropped.
- `no_args_is_help=True` makes bare `promptc` show help instead of a usage error.
- The existing `version` subcommand (lines 77–80) stays for back-compat.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_cli_phase1.py::test_version_flag_prints_version -v`
Expected: PASS.

- [ ] **Step 5: Verify help text and that subcommands still work**

Run: `python -m cli.main --help`
Expected: exit 0; root help now shows the "prcompiler — turn messy…" description and the `--version` option.
Run: `python -m cli.main version`
Expected: exit 0; prints the version (subcommand still works).

- [ ] **Step 6: Commit**

```bash
git add cli/commands/core.py tests/test_cli_phase1.py
git commit -m "feat(cli): add --version flag and inviting root help"
```

---

## Task 3: Fix the version lookup broken by the prcompiler rename

**Files:**
- Modify: `app/__init__.py` (line 14)

Context: `app/__init__.py` resolves `__version__` via `importlib.metadata.version("promptc")`. After #843 the distribution is `prcompiler`, so on an installed package this raises `PackageNotFoundError` and falls back to `0.0.0-dev`. This task corrects the distribution name. (Verified by grep that `app/__init__.py:14` is the ONLY code reference to the `promptc` distribution name; the `"promptc"` strings in `integrations/vscode-extension/*` are the VS Code settings namespace and are intentionally left alone.)

- [ ] **Step 1: Apply the one-line fix**

In `app/__init__.py`, change line 14 from:

```python
        __version__ = version("promptc")  # Distribution name as defined in pyproject
```

to:

```python
        __version__ = version("prcompiler")  # Distribution name as defined in pyproject
```

- [ ] **Step 2: Run the full test suite to confirm nothing regresses**

Run: `python -m pytest tests/ -q`
Expected: all green (this change only affects the distribution-name string used for metadata lookup). The real proof comes from the install smoke test in Task 5.

- [ ] **Step 3: Commit**

```bash
git add app/__init__.py
git commit -m "fix: resolve __version__ from prcompiler distribution name after rename"
```

---

## Task 4: Add a CLI install section to the README

**Files:**
- Modify: `README.md` (under `## Installation`, currently at line 281; today it only shows the dev/source setup)

- [ ] **Step 1: Insert the CLI install subsection**

Immediately after the `## Installation` heading line (line 281) and before the existing ```` ```bash ```` dev block, insert:

```markdown
### CLI (pip / pipx)

Install the command-line compiler from PyPI:

```bash
pipx install prcompiler        # recommended — isolated install
# or
pip install prcompiler
```

Then compile a prompt:

```bash
promptc compile "write a haiku about the sea"
promptc --version
```

### From source (development)
```

(The existing ```` ```bash ```` block with `git clone` … `npm ci` now sits under the new "From source (development)" subheading.)

- [ ] **Step 2: Verify the Markdown renders sensibly**

Run: `sed -n '281,310p' README.md`
Expected: `## Installation` → `### CLI (pip / pipx)` block → `### From source (development)` → original dev block.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add prcompiler CLI install section"
```

---

## Task 5: Clean-venv install smoke test (merge gate)

This is the authoritative check that the published wheel actually works. No code changes unless it surfaces a missing data file.

- [ ] **Step 1: Build the wheel into the scratchpad**

```bash
SCRATCH="/private/tmp/claude-501/-Users-mehmetozel-Developer-personal-Compiler/23364b9e-b080-4fdf-bcd9-67c530a7cb8f/scratchpad"
rm -rf "$SCRATCH/dist" "$SCRATCH/smoke-venv"
python -m build --wheel --outdir "$SCRATCH/dist"
```
Expected: `$SCRATCH/dist/prcompiler-2.0.46-py3-none-any.whl` produced.

- [ ] **Step 2: Install it into a fresh, isolated virtualenv**

```bash
python -m venv "$SCRATCH/smoke-venv"
"$SCRATCH/smoke-venv/bin/pip" install --quiet "$SCRATCH"/dist/prcompiler-*.whl
```
Expected: install completes; the `promptc` console script lands in `$SCRATCH/smoke-venv/bin/`.

- [ ] **Step 3: Verify help, version, and a real compile run**

```bash
"$SCRATCH/smoke-venv/bin/promptc" --help
"$SCRATCH/smoke-venv/bin/promptc" --version
"$SCRATCH/smoke-venv/bin/promptc" compile "write a haiku about the sea"
```
Expected:
- `--help`: exit 0, no `favorites/snippets/collections/palette`.
- `--version`: prints `2.0.46` (NOT `0.0.0-dev` — this proves Task 3).
- `compile`: exit 0, produces a System/User/Plan/Expanded output with no missing-file traceback (exercises `importlib.resources` templates + `_schemas` package-data).

- [ ] **Step 4 (contingency): If `compile` crashes on a missing data file**

Add the missing glob to `[tool.setuptools.package-data]` in `pyproject.toml` (e.g. another `app/_schemas/*.json` or template path), rebuild (Step 1), reinstall (Step 2), retest (Step 3). Commit:

```bash
git add pyproject.toml
git commit -m "fix(packaging): include missing data files in wheel"
```
Expected if no crash: skip this step.

---

## Task 6: Full suite green + open draft PR

- [ ] **Step 1: Run the full backend test suite**

Run: `python -m pytest tests/ -q`
Expected: all green.

- [ ] **Step 2: Push the branch**

Run: `git push -u origin feat/cli-phase1-vitrin-kurulum`

- [ ] **Step 3: Open a DRAFT PR**

```bash
gh pr create --draft --base main --head feat/cli-phase1-vitrin-kurulum \
  --title "CLI Phase 1: vitrin & kurulum" \
  --body "Phase 1 of the CLI cleanup ahead of the prcompiler PyPI launch. Removes 4 deprecated stub commands, adds --version + inviting help, fixes the version lookup left over from the #843 rename, adds a README CLI install section. Includes a clean-venv install smoke test (promptc --version -> 2.0.46, compile runs). Scope: cli/ + README + one line in app/__init__.py. Spec: docs/superpowers/specs/2026-06-24-cli-phase1-vitrin-kurulum-design.md"
```

- [ ] **Step 4: Report to the user**

Report changed files, smoke-test results, and CI status. Do NOT mark ready / merge without explicit approval.

---

## Self-Review (completed by author)

- **Spec coverage:** (A) deprecated removal → Task 1. (B) install verify + README → Tasks 4 & 5. (C) `--version` + help → Task 2. Bonus version bugfix → Task 3 (flagged deviation). All covered.
- **Placeholder scan:** none — every code/edit step shows concrete content; Task 4 contingency and Task 5 Step 4 are explicit conditionals, not placeholders.
- **Type/name consistency:** `_version_callback`, `_main`, `get_version()`, `app`, `runner`, `DEPRECATED` used consistently across tasks; `get_version` imported in both `cli/commands/core.py` (existing) and the test (Task 2 Step 1).
- **Test reality:** `tests/test_favorites.py` confirmed to test `app/favorites.py`, not the CLI stub — left untouched. No existing test asserts the old help string or the `version` subcommand output, so Task 2's changes don't break current tests.
