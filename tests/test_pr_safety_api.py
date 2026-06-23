from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from api.main import app
from app.pr_safety.analyzer import analyze_pr_safety

client = TestClient(app)

FIXTURE_PAYLOAD = {
    "title": "feat: add login flow",
    "description": "Add session-based login endpoints for the API.",
    "changed_files": [
        "api/routes/auth.py",
        "tests/test_auth.py",
    ],
}


def test_pr_safety_report_returns_expected_json_shape():
    response = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] in {"merge", "hold", "split", "rebase"}
    assert data["title"] == FIXTURE_PAYLOAD["title"]
    assert data["changed_files"]["total"] == 2
    assert "groups" in data["changed_files"]
    assert "hits" in data["risky_areas"]
    assert "gaps" in data["test_coverage"]
    assert "status" in data["branch_freshness"]
    assert "status" in data["scope_match"]
    assert isinstance(data["recommendations"], list)


def test_pr_safety_report_matches_offline_analyzer_fixture():
    response = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)
    expected = analyze_pr_safety(
        FIXTURE_PAYLOAD["title"],
        FIXTURE_PAYLOAD["description"],
        FIXTURE_PAYLOAD["changed_files"],
    )

    assert response.status_code == 200
    assert response.json() == json.loads(expected.model_dump_json())


def test_pr_safety_report_is_deterministic_for_fixture_input():
    first = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)
    second = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_pr_safety_report_accepts_optional_commits_behind():
    payload = {**FIXTURE_PAYLOAD, "commits_behind": 12}
    response = client.post("/pr-safety/report", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "rebase"
    assert data["branch_freshness"]["commits_behind"] == 12
    assert data["branch_freshness"]["status"] == "stale"


def test_pr_safety_report_omits_commits_behind_by_default():
    response = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["branch_freshness"]["status"] == "unknown"
    assert response.json()["branch_freshness"]["commits_behind"] is None


def test_pr_safety_report_validation_error_when_required_fields_missing():
    response = client.post("/pr-safety/report", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    missing_fields = {item["loc"][-1] for item in detail}
    assert missing_fields == {"title", "description", "changed_files"}


def test_pr_safety_report_validation_error_when_changed_files_empty():
    response = client.post(
        "/pr-safety/report",
        json={
            "title": "docs: update README",
            "description": "Refresh contributor docs.",
            "changed_files": [],
        },
    )

    assert response.status_code == 422


def test_pr_safety_report_does_not_require_external_api_keys(monkeypatch):
    for key in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "ADMIN_API_KEY",
        "PROMPTC_SERVER_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    response = client.post("/pr-safety/report", json=FIXTURE_PAYLOAD)

    assert response.status_code == 200
    assert os.environ.get("OPENROUTER_API_KEY") is None
