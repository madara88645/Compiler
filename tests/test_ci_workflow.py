from pathlib import Path

import yaml


def _load_ci_workflow() -> dict:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_ci_workflow_uploads_canonical_coverage_artifact_once():
    workflow = _load_ci_workflow()
    steps = workflow["jobs"]["full-test"]["steps"]

    upload_step = next(
        (
            step
            for step in steps
            if step.get("name") == "Upload canonical coverage artifact"
            and step.get("uses") == "actions/upload-artifact@v7"
        ),
        None,
    )

    assert upload_step is not None, "Canonical coverage upload step is missing"
    assert (
        upload_step.get("if") == "matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'"
    )
    assert upload_step.get("with", {}).get("name") == "coverage-canonical-py3.12"
    assert upload_step.get("with", {}).get("path") == "coverage.xml"


def test_ci_workflow_aligns_codecov_with_canonical_coverage_upload():
    workflow = _load_ci_workflow()
    steps = workflow["jobs"]["full-test"]["steps"]

    codecov_step = next(
        (
            step
            for step in steps
            if step.get("name") == "Upload coverage to Codecov"
            and step.get("uses") == "codecov/codecov-action@v6"
        ),
        None,
    )

    assert codecov_step is not None, "Codecov step is missing"
    assert (
        codecov_step.get("if") == "matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'"
    )
