#!/usr/bin/env python3
"""CLCD checker for dependency drift and installation health."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REQ_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*([^#\s]+)?")


def parse_requirements(requirements_path: Path) -> dict[str, list[str]]:
    deps: dict[str, list[str]] = {}
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = REQ_LINE_RE.match(line)
        if not match:
            continue
        name = match.group(1).lower().replace("_", "-")
        spec = (match.group(2) or "").strip()
        deps.setdefault(name, []).append(spec)
    return deps


def parse_pyproject_deps(pyproject_path: Path) -> dict[str, str]:
    deps: dict[str, str] = {}
    inside = False
    for raw in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "dependencies = [":
            inside = True
            continue
        if inside and line == "]":
            break
        if not inside:
            continue
        if not line.startswith('"'):
            continue
        item = line.rstrip(",").strip('"')
        match = re.match(r"^([A-Za-z0-9_.\-]+)(.*)$", item)
        if not match:
            continue
        name = match.group(1).lower().replace("_", "-")
        spec = match.group(2).strip()
        deps[name] = spec
    return deps


def run_pip_check() -> tuple[int, str]:
    process = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (process.stdout + process.stderr).strip()
    return process.returncode, output


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    requirements_path = repo_root / "requirements.txt"
    pyproject_path = repo_root / "pyproject.toml"

    reqs = parse_requirements(requirements_path)
    pyproject = parse_pyproject_deps(pyproject_path)

    errors: list[str] = []
    warnings: list[str] = []

    for name, specs in sorted(reqs.items()):
        unique_specs = sorted(set(specs))
        if len(unique_specs) > 1:
            errors.append(
                f"conflicting constraints for '{name}': {', '.join(unique_specs)}"
            )

    for name, spec in sorted(pyproject.items()):
        if name not in reqs:
            warnings.append(f"'{name}{spec}' exists in pyproject.toml but not requirements.txt")
            continue
        req_spec = reqs[name][0]
        if spec and spec != req_spec:
            warnings.append(
                f"'{name}' uses '{spec}' in pyproject.toml but '{req_spec}' in requirements.txt"
            )

    pip_check_rc, pip_check_output = run_pip_check()
    if pip_check_rc != 0:
        errors.append("pip check reported broken requirements")

    print("CLCD dependency report")
    print("======================")
    print(f"Scanned: {len(reqs)} requirements, {len(pyproject)} pyproject dependencies")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")

    if pip_check_output:
        print("\n`pip check` output:")
        print(pip_check_output)

    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nNo blocking CLCD issues found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
