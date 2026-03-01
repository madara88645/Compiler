#!/usr/bin/env python3
"""CLCD (Component Lifecycle Dependency Checker) report generator.

Checks:
- Python dependency declaration drift between `pyproject.toml` and `requirements.txt`
- Python dependency installation visibility via `pip freeze`
- Web dependency installation visibility via `npm ls --all --json`
- Duplicate direct dependency declarations in `web/package.json`
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


@dataclass
class Issue:
    issue_id: int
    severity: str
    description: str
    recommendation: str


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _normalize_pkg_name(raw: str) -> str:
    lowered = raw.strip().lower().replace("_", "-")
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", " "):
        if sep in lowered:
            lowered = lowered.split(sep, 1)[0]
            break
    return lowered


def load_python_declared() -> set[str]:
    pyproject = ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    return {_normalize_pkg_name(dep) for dep in deps}


def load_python_declared_all() -> set[str]:
    """Like load_python_declared but also includes optional-dependencies extras."""
    pyproject = ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    deps = list(project.get("dependencies", []))
    for extra_deps in project.get("optional-dependencies", {}).values():
        deps.extend(extra_deps)
    return {_normalize_pkg_name(dep) for dep in deps}


def load_python_requirements() -> set[str]:
    req = ROOT / "requirements.txt"
    out: set[str] = set()
    for line in req.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.add(_normalize_pkg_name(stripped))
    return out


def load_python_installed() -> set[str]:
    code, stdout, _stderr = _run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT)
    if code != 0:
        return set()
    return {_normalize_pkg_name(line) for line in stdout.splitlines() if line.strip()}


def load_web_direct_deps() -> tuple[set[str], set[str], set[str]]:
    package_json = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    deps = set(package_json.get("dependencies", {}).keys())
    dev_deps = set(package_json.get("devDependencies", {}).keys())
    overlap = deps.intersection(dev_deps)
    return deps, dev_deps, overlap


def npm_tree_ok() -> tuple[bool, str]:
    code, stdout, stderr = _run(["npm", "ls", "--all", "--json"], cwd=WEB)
    if code == 0:
        return True, "npm dependency tree resolved"

    problems: list[str] = []
    try:
        payload = json.loads(stdout) if stdout.strip() else {}
        raw_problems = payload.get("problems", [])
        problems = [str(item) for item in raw_problems][:5]
    except json.JSONDecodeError:
        problems = []

    if problems:
        return False, "npm dependency tree problems: " + "; ".join(problems)

    combined = (stdout + "\n" + stderr).lower()
    if "extraneous" in combined or "missing" in combined or "invalid" in combined:
        return False, "npm dependency tree reported missing/extraneous/invalid packages"
    return False, "npm ls command failed to verify dependency tree"


def build_issues() -> list[Issue]:
    issues: list[Issue] = []

    declared = load_python_declared()
    declared_all = load_python_declared_all()
    required = load_python_requirements()
    installed = load_python_installed()

    only_pyproject = sorted(declared - required)
    only_requirements = sorted(required - declared_all)

    issue_id = 1
    if only_pyproject:
        issues.append(
            Issue(
                issue_id,
                "Medium",
                "Dependencies declared in pyproject.toml but absent from requirements.txt: "
                + ", ".join(only_pyproject),
                "Sync requirements.txt with project.dependencies or switch CI installs to `pip install -e .` only.",
            )
        )
        issue_id += 1

    if only_requirements:
        issues.append(
            Issue(
                issue_id,
                "Medium",
                "Dependencies present in requirements.txt but absent from pyproject.toml: "
                + ", ".join(only_requirements),
                "Either move these into project.dependencies or mark them clearly as environment-only/runtime extras.",
            )
        )
        issue_id += 1

    if declared and installed:
        missing_installed = sorted(declared - installed)
        if missing_installed:
            issues.append(
                Issue(
                    issue_id,
                    "High",
                    "Declared Python dependencies not visible in current environment (`pip freeze`): "
                    + ", ".join(missing_installed),
                    "Install dependencies using `pip install -r requirements.txt` and `pip install -e .` before running checks.",
                )
            )
            issue_id += 1

    _deps, _dev_deps, overlap = load_web_direct_deps()
    if overlap:
        issues.append(
            Issue(
                issue_id,
                "Low",
                "Dependencies duplicated in both dependencies and devDependencies: "
                + ", ".join(sorted(overlap)),
                "Keep each package in a single section to avoid ambiguous lifecycle ownership.",
            )
        )
        issue_id += 1

    ok, tree_msg = npm_tree_ok()
    if not ok:
        issues.append(
            Issue(
                issue_id,
                "High",
                tree_msg,
                "Run `npm ci` in web/ and resolve missing or invalid packages reported by npm.",
            )
        )

    return issues


def format_report(issues: list[Issue]) -> str:
    header = "# CLCD Fixer Report\n\n"
    if not issues:
        return header + "No CLCD issues found.\n"

    table = [
        "| Issue ID | Severity | Description | Recommended Fix |",
        "| --- | --- | --- | --- |",
    ]
    for issue in issues:
        table.append(
            f"| {issue.issue_id} | {issue.severity} | {issue.description} | {issue.recommendation} |"
        )
    return header + "\n".join(table) + "\n"


def main() -> int:
    issues = build_issues()
    report = format_report(issues)
    print(report)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
