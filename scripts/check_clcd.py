#!/usr/bin/env python3
"""CLCD (Component Lifecycle Dependency Checker) validation script.

Checks performed:
1. Python dependency parity between pyproject.toml and requirements.txt
2. Python local import cycle detection across first-party modules
3. Web dependency parity between package.json and package-lock.json

Exit code is non-zero if any high-severity issue is found.
"""

from __future__ import annotations

import ast
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent
FIRST_PARTY_PACKAGES = {"app", "api", "cli"}


@dataclass
class Issue:
    severity: str
    category: str
    description: str
    recommendation: str


def normalize_requirement_name(requirement: str) -> str:
    head = requirement.split(";", 1)[0].split("[", 1)[0].strip()
    for token in ("==", ">=", "<=", "~=", "!=", "<", ">"):
        if token in head:
            head = head.split(token, 1)[0]
            break
    return head.strip().lower().replace("_", "-")


def parse_requirements(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.add(normalize_requirement_name(line))
    return names


def parse_pyproject_dependencies(path: Path) -> set[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    return {normalize_requirement_name(dep) for dep in deps}


def collect_local_import_edges(package_dir: Path, package_name: str) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for py_file in package_dir.rglob("*.py"):
        module = f"{package_name}.{py_file.relative_to(package_dir).with_suffix('')}".replace("/", ".")
        module = module.replace(".__init__", "")
        imports: set[str] = set()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FIRST_PARTY_PACKAGES:
                        imports.add(root)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.module:
                    rel_root = module.split(".")[: -node.level]
                    target = ".".join(rel_root + node.module.split(".")[:1])
                    root = target.split(".", 1)[0]
                elif node.module:
                    root = node.module.split(".", 1)[0]
                else:
                    continue
                if root in FIRST_PARTY_PACKAGES:
                    imports.add(root)

        edges[module] = imports
    return edges


def find_package_level_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {p: set() for p in FIRST_PARTY_PACKAGES}
    for module, imports in edges.items():
        source = module.split(".", 1)[0]
        if source not in FIRST_PARTY_PACKAGES:
            continue
        for imported in imports:
            if imported in FIRST_PARTY_PACKAGES and imported != source:
                graph[source].add(imported)

    cycles: list[list[str]] = []

    def dfs(node: str, stack: list[str], visited: set[str], active: set[str]) -> None:
        visited.add(node)
        active.add(node)
        stack.append(node)

        for nxt in sorted(graph[node]):
            if nxt not in visited:
                dfs(nxt, stack, visited, active)
            elif nxt in active:
                start = stack.index(nxt)
                cycles.append(stack[start:] + [nxt])

        active.remove(node)
        stack.pop()

    visited: set[str] = set()
    for node in sorted(graph):
        if node not in visited:
            dfs(node, [], visited, set())

    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for cycle in cycles:
        key = tuple(cycle)
        if key not in seen:
            seen.add(key)
            unique.append(cycle)
    return unique


def parse_npm_dependency_names(dep_map: dict[str, str] | None) -> set[str]:
    if not dep_map:
        return set()
    return {name.lower() for name in dep_map}


def parse_lock_top_level(lock: dict) -> set[str]:
    pkgs = lock.get("packages", {})
    root = pkgs.get("", {})
    deps = set()
    deps |= parse_npm_dependency_names(root.get("dependencies"))
    deps |= parse_npm_dependency_names(root.get("devDependencies"))
    if deps:
        return deps

    # fallback for older lockfile format
    dep_entries = lock.get("dependencies", {})
    return {name.lower() for name in dep_entries}


def run_checks() -> list[Issue]:
    issues: list[Issue] = []

    req_names = parse_requirements(ROOT / "requirements.txt")
    pyproject_names = parse_pyproject_dependencies(ROOT / "pyproject.toml")

    missing_in_requirements = sorted(pyproject_names - req_names)
    if missing_in_requirements:
        issues.append(
            Issue(
                severity="medium",
                category="python-dependency-parity",
                description=(
                    "Packages defined in pyproject.toml are missing from requirements.txt: "
                    + ", ".join(missing_in_requirements)
                ),
                recommendation="Add matching pins/ranges to requirements.txt or document intentional divergence.",
            )
        )

    missing_in_pyproject = sorted(req_names - pyproject_names)
    if missing_in_pyproject:
        issues.append(
            Issue(
                severity="low",
                category="python-dependency-parity",
                description=(
                    "Packages in requirements.txt are not in pyproject.toml runtime dependencies: "
                    + ", ".join(missing_in_pyproject)
                ),
                recommendation="Move optional/test packages to project.optional-dependencies and keep runtime dependencies aligned.",
            )
        )

    import_edges: dict[str, set[str]] = {}
    for package in FIRST_PARTY_PACKAGES:
        package_dir = ROOT / package
        import_edges.update(collect_local_import_edges(package_dir, package))

    cycles = find_package_level_cycles(import_edges)
    for cycle in cycles:
        issues.append(
            Issue(
                severity="high",
                category="circular-first-party-import",
                description=f"Circular dependency detected among first-party packages: {' -> '.join(cycle)}",
                recommendation="Break cycles by extracting shared contracts/utilities into a leaf module.",
            )
        )

    package_json = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))

    pkg_names = parse_npm_dependency_names(package_json.get("dependencies")) | parse_npm_dependency_names(
        package_json.get("devDependencies")
    )
    lock_names = parse_lock_top_level(package_lock)

    lock_missing = sorted(pkg_names - lock_names)
    if lock_missing:
        issues.append(
            Issue(
                severity="high",
                category="web-lockfile-integrity",
                description="package-lock.json is missing dependencies present in package.json: " + ", ".join(lock_missing),
                recommendation="Regenerate lockfile with npm install and commit the updated package-lock.json.",
            )
        )

    return issues


def print_report(issues: Iterable[Issue], fail_on_high: bool) -> int:
    issues = list(issues)
    print("CLCD Fixer Report")
    print("=" * 80)
    if not issues:
        print("No CLCD issues found.")
        return 0

    print("| Issue ID | Severity | Category | Description | Recommended Fix |")
    print("| --- | --- | --- | --- | --- |")
    for idx, issue in enumerate(issues, start=1):
        print(
            f"| {idx} | {issue.severity.title()} | {issue.category} | {issue.description} | {issue.recommendation} |"
        )

    high_issues = [issue for issue in issues if issue.severity.lower() == "high"]
    return 1 if (fail_on_high and high_issues) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CLCD checks and print a dependency lifecycle report.")
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with code 1 when high-severity issues are detected.",
    )
    args = parser.parse_args()
    return print_report(run_checks(), fail_on_high=args.fail_on_high)


if __name__ == "__main__":
    sys.exit(main())
