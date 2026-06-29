"""Threshold tests for POST /pr-safety/report/export (Codex task).

The PR Safety markdown renderer (app/pr_safety/markdown.py::report_to_markdown) is
GitHub-ready but currently CLI-only. Expose it through the API, mirroring
POST /compile/export, so web/CI/GitHub-Action consumers can fetch the server-side
markdown + structured JSON.

Do NOT modify, weaken, or delete any assertion in this file. The full existing
suite must also stay green.

Contract being locked in:
  * POST /pr-safety/report/export  (same request body as /pr-safety/report)
      -> { "markdown": str, "json": dict, "filename": str }
  * markdown is report_to_markdown(report) — same offline GitHub-ready document.
  * json is the structured PrSafetyReport (identical to /pr-safety/report).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

PAYLOAD = {
    "title": "Add OAuth login",
    "description": "Implements POST /login with password authentication and session tokens.",
    "changed_files": ["app/auth/login.py", "app/auth/session.py", "tests/test_login.py"],
    "commits_behind": 2,
}

VALID_VERDICTS = {"merge", "hold", "split", "rebase"}


def _export() -> dict:
    resp = client.post("/pr-safety/report/export", json=PAYLOAD)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_pr_safety_export_returns_markdown_json_filename():
    body = _export()
    assert isinstance(body.get("markdown"), str) and body["markdown"].strip()
    assert isinstance(body.get("json"), dict) and body["json"]
    assert isinstance(body.get("filename"), str) and body["filename"].endswith(".md")


def test_pr_safety_export_markdown_has_sections():
    md = _export()["markdown"]
    assert "# PR Safety Report" in md
    assert "**Verdict:**" in md
    assert "## Changed files" in md
    assert "## Risky areas" in md


def test_pr_safety_export_json_matches_report_endpoint():
    report = client.post("/pr-safety/report", json=PAYLOAD)
    assert report.status_code == 200, report.text
    report_json = report.json()
    exported = _export()["json"]
    assert exported["verdict"] in VALID_VERDICTS
    assert exported["verdict"] == report_json["verdict"]
    assert exported["title"] == PAYLOAD["title"]
    assert exported["changed_files"]["total"] == report_json["changed_files"]["total"]


def test_pr_safety_export_markdown_embeds_real_report_data():
    # Anti-gaming: the rendered markdown reflects the actual report input,
    # not a hardcoded template.
    assert PAYLOAD["title"] in _export()["markdown"]
