# PyPI release checklist (`prcompiler`)

Operational guide for cutting a `prcompiler` release on PyPI via
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) and GitHub
trusted publishing (OIDC). This document was written after reproducing the
local build and reviewing the workflow against current PyPI requirements (July
2026).

**Scope:** documentation and human steps only. This checklist does **not** push
tags or publish packages.

---

## Findings (July 2026 audit)

### Local build reproduction

On this repo at `pyproject.toml` version **2.0.46**:

```bash
python -m pip install --upgrade pip build
python -m build
```

| Result | Detail |
|--------|--------|
| **Status** | Succeeds on Python 3.12 |
| **Wheel** | `dist/prcompiler-2.0.46-py3-none-any.whl` (~422 KB) |
| **Sdist** | `dist/prcompiler-2.0.46.tar.gz` (~568 KB) |
| **Entry point** | `promptc = cli.main:app` (from `pyproject.toml`) |

The build matches what CI runs in `publish.yml` (install `build`, then
`python -m build`).

**Hygiene notes (non-blocking for first publish, worth fixing later):**

- The wheel currently includes `web/node_modules/flatted/python/flatted.py`
  because setuptools package discovery is broad. Consider tightening
  `exclude` / `packages.find` before shipping a “clean” public artifact.
- `python -m twine check dist/*` may warn on `License-File` metadata
  (Metadata-Version 2.4) depending on the local `twine` version. PyPI’s upload
  path used by `pypa/gh-action-pypi-publish` generally accepts current
  setuptools output.

### Tag ↔ version drift

| Source | Version |
|--------|---------|
| `pyproject.toml` | **2.0.46** |
| Latest git tag | **v2.0.6** (2025-09-04 era) |
| `CHANGELOG.md` top entry | **2.0.46** (2026-05-08) |

Tags were never advanced to match the current package version. Pushing an old
tag (e.g. `v2.0.6`) would publish **2.0.46** from `pyproject.toml` on `main`,
which is confusing and makes rollback forensics harder. **Always align the tag
name with `pyproject.toml` before pushing.**

### PyPI project state

- `https://pypi.org/project/prcompiler/` returns **404** — the project has
  **never** been published successfully.
- The only recorded `Publish to PyPI` workflow run used tag **`v2`** (2026-02-08)
  and **failed**; logs have expired.
- For a net-new project name, PyPI requires a **pending** trusted publisher
  (not “add publisher on existing project”). See [Creating a PyPI project with a
  Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

### Workflow review vs trusted-publishing requirements

File: [`.github/workflows/publish.yml`](../.github/workflows/publish.yml)

| Requirement (PyPI / PyPA) | Workflow status |
|---------------------------|-----------------|
| Trigger on release tag | `on.push.tags: "v*"` |
| `pypa/gh-action-pypi-publish@release/v1` | Present |
| No `username` / `password` / long-lived API token | Correct for OIDC |
| `id-token: write` permission | Present (workflow-level; PyPI docs prefer **job-level**, but workflow-level works) |
| GitHub `environment: pypi` | Present — **must match** PyPI publisher config if you set an environment there |
| Trusted publisher fields on PyPI | **Must be configured by a human** (see below) |

**Trusted publisher values that must match exactly:**

| Field | Value |
|-------|-------|
| PyPI project name | `prcompiler` |
| GitHub owner | `madara88645` |
| GitHub repository | `Compiler` (canonical; GitHub redirects from `compiler`) |
| Workflow filename | `publish.yml` (filename only, not the full path) |
| GitHub environment (recommended) | `pypi` |

**Likely failure causes for the `v2` run (inferred):**

1. No PyPI trusted publisher (or pending publisher) for `prcompiler`.
2. GitHub environment `pypi` missing or misconfigured.
3. Tag `v2` did not match package version **2.0.46** (process gap, not a hard
   CI failure).
4. Possible OIDC mismatch if PyPI was configured with a different workflow
   name, repository name (note canonical repo is **`Compiler`**, not `compiler`),
   or environment than the workflow uses.

**Optional hardening (future PRs, not required for first publish):**

- Move `permissions.id-token: write` to the `build-and-publish` job.
- Add `environment.url: https://pypi.org/project/prcompiler/`.
- Upload `dist/*` as a workflow artifact before publish (debugging).
- Add a pre-publish step that asserts the tag matches `pyproject.toml` version.

---

## Prerequisites

- [ ] Maintainer access to `madara88645/Compiler` on GitHub.
- [ ] PyPI account with permission to register **`prcompiler`** (name is
  unclaimed as of this audit).
- [ ] `main` is green in CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).
- [ ] `pyproject.toml`, `CHANGELOG.md`, and any user-facing version strings
  agree on the release version.

---

## Step 1 — Align tag ↔ version

The tag **must** be `v` + the exact `version` in `pyproject.toml`.

**Example for 2.0.46:**

1. Confirm version in `pyproject.toml`:

   ```bash
   grep '^version' pyproject.toml
   # version = "2.0.46"
   ```

2. Confirm `CHANGELOG.md` has a `## [2.0.46]` section with the correct date.

3. Commit any last-minute release prep on `main` (version bumps, changelog).

4. Create an **annotated** tag locally (do not push until Steps 2–3 are done):

   ```bash
   git tag -a v2.0.46 -m "Release prcompiler 2.0.46"
   ```

5. Verify:

   ```bash
   git tag -l 'v2.0.46'
   python -m pip install build
   python -m build
   ls dist/prcompiler-2.0.46*
   ```

**Convention:** use semantic tags `vMAJOR.MINOR.PATCH` (e.g. `v2.0.46`). Avoid
bare tags like `v2` — they trigger the workflow but do not document the shipped
version.

---

## Step 2 — PyPI: pending trusted publisher (human-owned)

Because `prcompiler` does not exist on PyPI yet, use a **pending** publisher.

1. Log in at [pypi.org](https://pypi.org/).
2. Open your **account** menu → **Publishing** (account-level, not a project
   page).
3. Under **GitHub**, click **Add a new pending publisher**.
4. Enter:

   | Field | Value |
   |-------|-------|
   | PyPI project name | `prcompiler` |
   | Owner | `madara88645` |
   | Repository name | `Compiler` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

5. Click **Add**. The pending publisher appears in the list.

6. **Important:** A pending publisher does **not** reserve the name until the
   first successful upload. If someone else registers `prcompiler` first, this
   publisher is invalidated — act promptly after configuration.

**After the first successful publish:** the pending publisher becomes a normal
project publisher on `https://pypi.org/manage/project/prcompiler/publishing/`.
No second PyPI setup is required for later releases unless you change workflow
or environment names.

References:

- [Creating a PyPI project with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [Adding a Trusted Publisher to an existing PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) (for subsequent config changes)

---

## Step 3 — GitHub: `pypi` environment (human-owned)

1. In GitHub: **madara88645/Compiler** → **Settings** → **Environments**.
2. Create environment **`pypi`** (name must match PyPI publisher config).
3. Recommended protection (optional but strongly advised):
   - **Required reviewers** — at least one maintainer approves each publish.
   - **Deployment branches** — restrict to tags matching `v*` or a specific
     release branch policy.
4. Do **not** add `PYPI_API_TOKEN` secrets for trusted publishing; OIDC replaces
   long-lived tokens.

The workflow already declares:

```yaml
environment: pypi
```

If PyPI lists environment `pypi` but GitHub has no environment with that name,
or names differ by even one character, OIDC exchange fails.

---

## Step 4 — Publish (human pushes the tag)

Only after Steps 2 and 3 are complete:

```bash
git push origin v2.0.46
```

This triggers **Publish to PyPI** via the `v*` tag filter.

**Expected CI flow:**

1. Checkout
2. Python 3.12 + `pip` cache
3. `python -m build` → `dist/prcompiler-<version>.*`
4. `pypa/gh-action-pypi-publish@release/v1` → OIDC token → PyPI upload

If the environment has required reviewers, approve the deployment in the
Actions run before the publish step executes.

**Verify success:**

- [https://pypi.org/project/prcompiler/](https://pypi.org/project/prcompiler/)
  shows the new version.
- `pip install prcompiler==<version>` works in a clean venv.
- `promptc --version` reports the installed version.

---

## Step 5 — Re-run or recover from a failed publish

`publish.yml` has **no** `workflow_dispatch`; releases are tag-driven only.

### Option A — Re-run an existing failed workflow

Use when the tag is already correct and PyPI/GitHub config is now fixed:

1. GitHub → **Actions** → **Publish to PyPI**.
2. Open the failed run (e.g. the historical `v2` run, if still listed).
3. **Re-run all jobs** (or re-run failed jobs).

This reuses the **same tag** and rebuilds from that tag’s commit. Only do this
if that commit is still the intended release.

### Option B — New tag after fixing config (recommended for `prcompiler`)

Given tag drift (`v2.0.6` vs `2.0.46`) and the failed `v2` run:

1. Complete Steps 2–3 (pending publisher + `pypi` environment).
2. Ensure `main` at the intended commit has `version = "2.0.46"`.
3. Tag `v2.0.46` (Step 1).
4. `git push origin v2.0.46`.

Do **not** re-push `v2` unless you deliberately want to publish whatever
`pyproject.toml` contains at that old commit.

### Option C — Tag was pushed but publish failed (no PyPI version published)

If PyPI shows **no** release for that version:

1. Fix PyPI/GitHub configuration.
2. Delete the remote tag only if no successful publish occurred:

   ```bash
   git push origin :refs/tags/v2.0.46
   git tag -d v2.0.46   # locally, if needed
   ```

3. Recreate and push the tag pointing at the correct commit.

**Warning:** Never delete or move a tag after a version is live on PyPI. PyPI
does not allow re-uploading the same version.

### Option D — Environment approval stuck

If the job waits on `pypi` environment review:

1. Open the workflow run → **Review deployments**.
2. Approve for environment `pypi`.

---

## Quick reference

| Item | Value |
|------|-------|
| Package name | `prcompiler` |
| Version source of truth | `pyproject.toml` → `[project].version` |
| Tag format | `v{version}` e.g. `v2.0.46` |
| Workflow | `.github/workflows/publish.yml` |
| PyPI publisher workflow filename | `publish.yml` |
| GitHub environment | `pypi` |
| Publish action | `pypa/gh-action-pypi-publish@release/v1` |
| Local build | `python -m pip install build && python -m build` |

---

## Related docs

- VS Code extension publishing (separate workflow/tags):
  [`integrations/vscode-extension/PUBLISHING.md`](../integrations/vscode-extension/PUBLISHING.md)
  Tags: `vscode-v*`, environment: `vscode-marketplace`.
- CLI Phase 1 design note on sequencing `v2.0.46`:
  [`docs/superpowers/specs/2026-06-24-cli-phase1-vitrin-kurulum-design.md`](superpowers/specs/2026-06-24-cli-phase1-vitrin-kurulum-design.md)
