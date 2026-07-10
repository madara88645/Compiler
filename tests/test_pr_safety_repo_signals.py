from __future__ import annotations

from pathlib import Path

from app.pr_safety.analyzer import analyze_pr_safety
from app.pr_safety.models import RepoAwarePrSafetyReport
from app.pr_safety.repo_signals import collect_repo_signals


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collects_owners_workflows_commands_and_stacks(tmp_path: Path) -> None:
    _write(
        tmp_path,
        ".github/CODEOWNERS",
        "* @general\n/app/* @backend @security\n",
    )
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        """name: Backend CI
on:
  pull_request:
    paths:
      - "app/**"
jobs:
  tests:
    runs-on: ubuntu-latest
""",
    )
    _write(
        tmp_path,
        "Makefile",
        "test:\n\tpython -m pytest tests/ -q\n",
    )
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "demo"\ndependencies = ["fastapi"]\n',
    )
    _write(
        tmp_path,
        "web/package.json",
        '{"scripts":{"test":"vitest run","lint":"eslint ."},"dependencies":{"next":"15"}}',
    )

    signals = collect_repo_signals(
        tmp_path,
        ["app/auth.py", "docs/guide.md"],
    )

    owners = {match.file: match.owners for match in signals.owners}
    assert owners == {
        "app/auth.py": ["@backend", "@security"],
        "docs/guide.md": ["@general"],
    }
    assert signals.owners[0].source == ".github/CODEOWNERS"

    assert len(signals.overlapping_workflows) == 1
    workflow = signals.overlapping_workflows[0]
    assert workflow.path == ".github/workflows/ci.yml"
    assert workflow.name == "Backend CI"
    assert workflow.jobs == ["tests"]
    assert workflow.matched_files == ["app/auth.py"]

    commands = {command.name: command for command in signals.detected_commands}
    assert commands["test"].command == "python -m pytest tests/ -q"
    assert commands["test"].source == "Makefile"
    assert commands["lint"].command == "npm run lint"

    stacks = {stack.language: set(stack.frameworks) for stack in signals.stacks}
    assert stacks == {"javascript": {"next"}, "python": {"fastapi"}}
    assert signals.warnings == []


def test_only_surfaces_pull_request_workflows_that_overlap_changes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        ".github/workflows/frontend.yml",
        """name: Frontend
on:
  pull_request:
    paths: ["web/**"]
jobs:
  test: {}
""",
    )
    _write(
        tmp_path,
        ".github/workflows/backend.yml",
        """name: Backend
on:
  pull_request:
    paths: ["app/**"]
jobs:
  test: {}
""",
    )
    _write(
        tmp_path,
        ".github/workflows/deploy.yml",
        """name: Deploy
on: push
jobs:
  deploy: {}
""",
    )

    signals = collect_repo_signals(tmp_path, ["app/compiler.py"])

    assert [workflow.path for workflow in signals.overlapping_workflows] == [
        ".github/workflows/backend.yml"
    ]


def test_malformed_workflow_is_a_relative_advisory_warning(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/broken.yml", "on: [pull_request\n")

    signals = collect_repo_signals(tmp_path, ["app/compiler.py"])

    assert len(signals.warnings) == 1
    assert ".github/workflows/broken.yml" in signals.warnings[0]
    assert str(tmp_path) not in signals.warnings[0]


def test_repo_signals_do_not_change_the_deterministic_verdict(tmp_path: Path) -> None:
    _write(tmp_path, "Makefile", "test:\n\tpytest -q\n")
    changed_files = ["app/compiler.py", "tests/test_compiler.py"]
    signals = collect_repo_signals(tmp_path, changed_files)

    baseline = analyze_pr_safety(
        title="refactor: compiler cleanup",
        description="Clean up compiler internals with matching tests.",
        changed_files=changed_files,
    )
    enriched = analyze_pr_safety(
        title="refactor: compiler cleanup",
        description="Clean up compiler internals with matching tests.",
        changed_files=changed_files,
        repo_signals=signals,
    )

    assert enriched.verdict == baseline.verdict
    assert isinstance(enriched, RepoAwarePrSafetyReport)
    assert enriched.repo_signals == signals
