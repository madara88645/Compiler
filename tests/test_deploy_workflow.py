from pathlib import Path

import yaml


def _load_deploy_workflow() -> dict:
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy.yml"
    )
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_deploy_workflow_only_runs_after_successful_ci_on_main():
    workflow = _load_deploy_workflow()
    trigger = workflow.get("on", workflow.get(True))

    assert "workflow_run" in trigger

    workflow_run = trigger["workflow_run"]
    assert workflow_run["workflows"] == ["CI"]
    assert workflow_run["types"] == ["completed"]

    deploy_job = workflow["jobs"]["deploy"]
    assert deploy_job["if"] == (
        "${{ github.event.workflow_run.conclusion == 'success' "
        "&& github.event.workflow_run.head_branch == 'main' "
        "&& github.event.workflow_run.event == 'push' }}"
    )


def test_deploy_workflow_checks_out_ci_tested_sha():
    workflow = _load_deploy_workflow()
    steps = workflow["jobs"]["deploy"]["steps"]
    checkout_step = next(
        (s for s in steps if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/checkout")),
        None,
    )
    assert checkout_step is not None, "No actions/checkout step found"
    assert checkout_step.get("with", {}).get("ref") == "${{ github.event.workflow_run.head_sha }}"
