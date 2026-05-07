from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


def _request_payload(pack_type: str) -> dict[str, str]:
    return {
        "project_type": "SaaS",
        "stack": "FastAPI + Next.js",
        "goal": "Create a repo-aware Claude workflow for this product.",
        "pack_type": pack_type,
        "risk_mode": "strict",
    }


def test_agent_packs_claude_project_pack_manifest_shape():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = (
            "# Review Agent\n\n## Role\nYou review code.\n\n## Goals\n- Catch prompt leaks"
        )

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=_request_payload("project-pack"))

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "claude"
        assert data["pack_type"] == "project-pack"
        assert data["download_name"] == "saas-project-pack-claude"
        assert "claude_md" in data["preview_order"]
        assert any(file["path"] == "CLAUDE.md" for file in data["files"])
        assert any(file["path"] == ".claude/settings.json" for file in data["files"])
        assert any(file["kind"] == "mcp" for file in data["files"])


def test_agent_packs_claude_subagent_manifest_shape():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = (
            "# React Performance Agent\n\n## Role\nYou optimize React apps."
        )

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=_request_payload("subagent"))

        assert response.status_code == 200
        data = response.json()
        assert data["pack_type"] == "subagent"
        assert len(data["files"]) == 2
        assert any(file["path"].startswith(".claude/agents/") for file in data["files"])
        assert any(file["path"] == "README.md" for file in data["files"])


def test_agent_packs_claude_pr_reviewer_manifest_shape():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = (
            "# PR Reviewer\n\n## Goals\n- Catch unsafe settings"
        )

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=_request_payload("pr-reviewer"))

        assert response.status_code == 200
        data = response.json()
        assert data["pack_type"] == "pr-reviewer"
        assert any(file["path"] == ".github/workflows/claude.yml" for file in data["files"])
        assert any(file["path"] == ".claude/agents/pr-reviewer.md" for file in data["files"])


def test_agent_packs_claude_mcp_stub_manifest_shape():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# search_docs - Skill Definition\n\n## Name\nsearch_docs\n\n## Purpose\nSearch project docs.\n"

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=_request_payload("mcp-tool-stub"))

        assert response.status_code == 200
        data = response.json()
        assert data["pack_type"] == "mcp-tool-stub"
        assert all(file["kind"] in {"mcp", "readme"} for file in data["files"])
        assert any(file["path"] == "server.py" for file in data["files"])


def test_agent_packs_download_returns_single_file_when_manifest_has_one_file():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = (
            "# search_docs - Skill Definition\n\n## Name\nsearch_docs\n\n## Purpose\nSearch docs."
        )

        client = TestClient(app)
        response = client.post(
            "/agent-packs/claude/download",
            json={**_request_payload("mcp-tool-stub"), "goal": "Build a single-file stub."},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        assert set(archive.namelist()) == {"server.py", "README.md"}


def test_agent_packs_download_returns_plain_file_for_single_file_manifest():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Review Agent\n\n## Role\nYou review code."

        with patch("app.adapters.agent_packs.to_claude_subagent_bundle") as mock_bundle:
            mock_bundle.return_value = [
                {"path": ".claude/agents/review-agent.md", "content": "hello"},
            ]
            client = TestClient(app)
            response = client.post(
                "/agent-packs/claude/download", json=_request_payload("subagent")
            )

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="review-agent.md"'
        assert response.text == "hello"
