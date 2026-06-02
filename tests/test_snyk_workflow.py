from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    pyproject_path = _repo_root() / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def _load_requirements() -> list[str]:
    requirements_path = _repo_root() / "requirements.txt"
    return [
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _load_snyk_workflow() -> dict:
    workflow_path = _repo_root() / ".github" / "workflows" / "snyk.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_runtime_manifests_match_exactly():
    pyproject = _load_pyproject()
    runtime_dependencies = sorted(pyproject["project"]["dependencies"])
    requirements = sorted(_load_requirements())

    assert runtime_dependencies == requirements


def test_snyk_workflow_scans_python_manifests_explicitly():
    workflow = _load_snyk_workflow()
    steps = workflow["jobs"]["snyk"]["steps"]

    install_step = next(
        (step for step in steps if step.get("name") == "Install dependencies"), None
    )
    assert install_step is not None, "Snyk install step is missing"
    assert "pip install -e ." not in install_step.get("run", "")

    requirements_scan = next(
        (step for step in steps if step.get("name") == "Run Snyk (requirements.txt)"), None
    )
    assert requirements_scan is not None, "requirements.txt Snyk scan step is missing"
    assert (
        requirements_scan.get("run")
        == "snyk test --file=requirements.txt --package-manager=pip --severity-threshold=high"
    )

    pyproject_scan = next(
        (step for step in steps if step.get("name") == "Run Snyk (pyproject.toml)"), None
    )
    assert pyproject_scan is not None, "pyproject.toml Snyk scan step is missing"
    assert (
        pyproject_scan.get("run")
        == "snyk test --file=pyproject.toml --package-manager=pip --severity-threshold=high"
    )
