from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app
from app.adapters.agent_packs import AgentPackManifest


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
        assert set(archive.namelist()) == {"server.py", "README.md", ".mcp.json"}


def test_agent_packs_download_multi_file_pack_returns_nonempty_zip():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = (
            "# Review Agent\n\n## Role\nYou review code.\n\n## Goals\n- Catch prompt leaks"
        )

        client = TestClient(app)
        response = client.post(
            "/agent-packs/claude/download", json=_request_payload("project-pack")
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
        assert "filename=" in response.headers["content-disposition"]
        assert 'filename="saas-project-pack-claude.zip"' in response.headers["content-disposition"]
        assert len(response.content) > 0

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        assert len(archive.namelist()) > 1
        # Every archived file should carry real content.
        assert all(archive.read(name) for name in archive.namelist())


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
        # The downloaded pack carries the readiness section (consistent with the manifest).
        assert response.text.startswith("hello")
        assert "## Readiness:" in response.text


def test_agent_packs_endpoint_validation_errors():
    client = TestClient(app)

    # Missing required fields
    response = client.post("/agent-packs/claude", json={})
    assert response.status_code == 422

    # Invalid pack_type
    response = client.post(
        "/agent-packs/claude",
        json={**_request_payload("invalid-pack-type"), "pack_type": "invalid-pack-type"},
    )
    assert response.status_code == 422


def test_agent_packs_compiler_exception_returns_500():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.side_effect = Exception("Simulated compiler error")

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=_request_payload("subagent"))

        assert response.status_code == 500
        assert response.json() == {"detail": "An internal error occurred."}


def test_agent_packs_download_exception_returns_500():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.side_effect = Exception("Simulated compiler error")

        client = TestClient(app)
        response = client.post("/agent-packs/claude/download", json=_request_payload("subagent"))

        assert response.status_code == 500
        assert response.json() == {"detail": "An internal error occurred."}


def test_agent_packs_risk_mode_balanced_vs_strict():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Agent"
        client = TestClient(app)

        # Test strict mode
        strict_payload = _request_payload("subagent")
        strict_payload["risk_mode"] = "strict"
        client.post("/agent-packs/claude", json=strict_payload)

        call_args = mock_compiler.generate_agent.call_args[0]
        assert "strict security defaults" in call_args[0]

        # Test balanced mode
        balanced_payload = _request_payload("subagent")
        balanced_payload["risk_mode"] = "balanced"
        client.post("/agent-packs/claude", json=balanced_payload)

        call_args = mock_compiler.generate_agent.call_args[0]
        assert "Balance usability" in call_args[0]


def test_agent_packs_download_media_types():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Agent"

        with patch("app.adapters.agent_packs.to_claude_subagent_bundle") as mock_bundle:
            # Test json
            mock_bundle.return_value = [
                {"path": ".claude/settings.json", "content": "{}"},
            ]
            client = TestClient(app)
            response = client.post(
                "/agent-packs/claude/download", json=_request_payload("subagent")
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            # Test python
            mock_bundle.return_value = [
                {"path": "script.py", "content": "print('hi')"},
            ]
            response = client.post(
                "/agent-packs/claude/download", json=_request_payload("subagent")
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/x-python; charset=utf-8"


def test_agent_pack_manifest_rejects_unknown_provider():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "cursor",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents"],
                "files": [
                    {
                        "path": ".claude/agents/review-agent.md",
                        "content": "hello",
                        "kind": "agents",
                    }
                ],
            }
        )


def test_agent_pack_manifest_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["ghost-kind"],
                "files": [
                    {
                        "path": ".claude/agents/review-agent.md",
                        "content": "hello",
                        "kind": "ghost-kind",
                    }
                ],
            }
        )


def test_agent_pack_manifest_rejects_preview_order_kinds_not_present_in_files():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents", "workflow"],
                "files": [
                    {
                        "path": ".claude/agents/review-agent.md",
                        "content": "hello",
                        "kind": "agents",
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        "   ",
        "../secrets.txt",
        "..\\secrets.txt",
        "/etc/passwd",
        "C:/windows/system32/config",
        ".claude/../secrets.txt",
    ],
)
def test_agent_pack_manifest_rejects_unsafe_file_paths(bad_path: str):
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents"],
                "files": [
                    {
                        "path": bad_path,
                        "content": "hello",
                        "kind": "agents",
                    }
                ],
            }
        )


def test_agent_pack_manifest_rejects_duplicate_file_paths():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents"],
                "files": [
                    {
                        "path": ".claude/agents/review-agent.md",
                        "content": "hello",
                        "kind": "agents",
                    },
                    {
                        "path": ".claude\\agents\\review-agent.md",
                        "content": "world",
                        "kind": "agents",
                    },
                ],
            }
        )
