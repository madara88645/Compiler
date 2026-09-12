from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_instruction_review_endpoint_is_public_and_returns_report_shape():
    response = client.post(
        "/instruction-review/analyze",
        json={
            "files": [
                {
                    "path": "CLAUDE.md",
                    "content": "# Rules\n- Keep changes small.\n- Keep changes small.\n",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"findings", "files", "summary"}
    assert payload["files"][0]["original"].startswith("# Rules")
    assert payload["files"][0]["suggested"].count("Keep changes small") == 1
    assert payload["files"][0]["diff"].startswith("--- CLAUDE.md\n+++ CLAUDE.md (suggested)\n@@")
    assert payload["summary"]["files_reviewed"] == 1
    assert payload["summary"]["findings_count"] == len(payload["findings"])


def test_instruction_review_endpoint_is_deterministic_and_does_not_write_back():
    body = {
        "files": [
            {
                "path": "AGENTS.md",
                "content": "- Never run `pytest -q`.\n- Always run `pytest -q`.\n",
            }
        ]
    }

    first = client.post("/instruction-review/analyze", json=body)
    second = client.post("/instruction-review/analyze", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["files"][0]["original"] == body["files"][0]["content"]
    assert first.json()["files"][0]["suggested"] == body["files"][0]["content"]


def test_instruction_review_endpoint_rejects_invalid_names_and_bounds():
    invalid_path = client.post(
        "/instruction-review/analyze",
        json={"files": [{"path": "../secrets.md", "content": "rules"}]},
    )
    assert invalid_path.status_code == 422

    too_many = client.post(
        "/instruction-review/analyze",
        json={"files": [{"path": f"rules-{index}.md", "content": "rules"} for index in range(13)]},
    )
    assert too_many.status_code == 422


def test_instruction_review_endpoint_keeps_unknown_links_unverified():
    response = client.post(
        "/instruction-review/analyze",
        json={"files": [{"path": "CLAUDE.md", "content": "See [guide](docs/guide.md)."}]},
    )

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["kind"] == "stale_link"
    assert finding["severity"] == "info"
    assert "not verified" in finding["message"]
