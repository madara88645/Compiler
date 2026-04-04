from pathlib import Path

import yaml


def _load_deploy_workflow() -> dict:
    workflow_path = Path(".github/workflows/deploy.yml")
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
        "&& github.event.workflow_run.head_branch == 'main' }}"
    )
