from __future__ import annotations

import asyncio
import io
import json
import time
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app
from api.routes.agent_packs import (
    RepoPlanRequest,
    build_claude_agent_pack,
    download_claude_agent_pack,
    repo_plan_claude_agent_pack,
)
from app.adapters.agent_packs import AgentPackManifest, AgentPackRequest
from app.repo_inspect import RepoFacts


def _request_payload(pack_type: str) -> dict[str, str]:
    return {
        "project_type": "SaaS",
        "stack": "FastAPI + Next.js",
        "goal": "Create a repo-aware Claude workflow for this product.",
        "pack_type": pack_type,
        "risk_mode": "strict",
    }


def _github_reviewer_payload() -> dict[str, str]:
    return {
        "project_type": "Python release automation",
        "stack": "Python, GitHub Actions, uv",
        "goal": "Review release pull requests for unsafe publishing steps, missing tests, and dependency drift.",
        "pack_type": "pr-reviewer",
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
        response = client.post("/agent-packs/claude", json=_github_reviewer_payload())

        assert response.status_code == 200
        data = response.json()
        assert data["pack_type"] == "pr-reviewer"
        files = {file["path"]: file for file in data["files"]}
        assert ".github/workflows/claude.yml" in files
        assert ".claude/agents/pr-reviewer.md" in files
        assert ".mcp.json" in files
        assert ".claude/hooks.example.json" in files

        mcp_config = json.loads(files[".mcp.json"]["content"])
        assert mcp_config["mcpServers"]["github"]["url"] == "https://api.githubcopilot.com/mcp/"

        hooks_config = json.loads(files[".claude/hooks.example.json"]["content"])
        post_tool_use = hooks_config["hooks"]["PostToolUse"]
        assert post_tool_use[0]["matcher"] == "Edit|Write"
        assert post_tool_use[0]["hooks"][0]["command"].startswith("echo ")

        settings = json.loads(files[".claude/settings.json"]["content"])
        assert "hooks" not in settings


def test_balanced_pr_reviewer_pack_stays_review_only():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# PR Reviewer\n\n## Role\nYou review code."

        payload = _github_reviewer_payload()
        payload["risk_mode"] = "balanced"

        client = TestClient(app)
        response = client.post("/agent-packs/claude", json=payload)

        assert response.status_code == 200
        files = {file["path"]: file for file in response.json()["files"]}

        reviewer = files[".claude/agents/pr-reviewer.md"]["content"]
        tool_line = next(line for line in reviewer.splitlines() if line.startswith("tools: "))
        assert tool_line == "tools: Read, Glob, Grep, Bash"

        settings = json.loads(files[".claude/settings.json"]["content"])
        assert settings["permissions"]["defaultMode"] == "default"
        assert "Bash(git commit:*)" in settings["permissions"]["ask"]


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
        response = client.post("/agent-packs/claude/download", json=_github_reviewer_payload())

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
        assert "filename=" in response.headers["content-disposition"]
        assert (
            'filename="python-release-automation-pr-reviewer-claude.zip"'
            in response.headers["content-disposition"]
        )
        assert len(response.content) > 0

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = set(archive.namelist())
        assert ".mcp.json" in names
        assert ".claude/hooks.example.json" in names
        # Every archived file should carry real content.
        assert all(archive.read(name) for name in names)

        mcp_config = json.loads(archive.read(".mcp.json"))
        assert (
            mcp_config["mcpServers"]["github"]["headers"]["Authorization"] == "Bearer ${GITHUB_PAT}"
        )

        hooks_config = json.loads(archive.read(".claude/hooks.example.json"))
        assert hooks_config["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"


def test_agent_packs_download_accepts_existing_manifest_without_regenerating():
    manifest = {
        "provider": "claude",
        "pack_type": "project-pack",
        "download_name": "existing-project-pack",
        "preview_order": ["claude_md", "settings"],
        "files": [
            {"path": "CLAUDE.md", "content": "# Existing pack", "kind": "claude_md"},
            {"path": ".claude/settings.json", "content": "{}", "kind": "settings"},
        ],
    }

    with patch("api.main.hybrid_compiler") as mock_compiler:
        response = TestClient(app).post("/agent-packs/claude/download", json=manifest)

    assert response.status_code == 200
    mock_compiler.generate_agent.assert_not_called()
    mock_compiler.generate_skill.assert_not_called()
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert set(archive.namelist()) == {"CLAUDE.md", ".claude/settings.json"}


@pytest.mark.parametrize("endpoint", [build_claude_agent_pack, download_claude_agent_pack])
def test_agent_pack_generation_does_not_block_other_async_work(endpoint):
    order: list[str] = []

    def generate(*args, **kwargs):
        time.sleep(0.06)
        order.append("generated")
        return "# Generated instructions"

    compiler = MagicMock()
    compiler.generate_agent.side_effect = generate
    request = AgentPackRequest.model_validate(_request_payload("project-pack"))

    async def check():
        async def tick():
            await asyncio.sleep(0.01)
            order.append("tick")

        await asyncio.gather(endpoint(request), tick())

    with patch("api.routes.agent_packs._get_compiler", return_value=compiler):
        asyncio.run(check())

    assert order == ["tick", "generated"]


def test_repo_plan_generation_does_not_block_other_async_work():
    order: list[str] = []

    def generate(*args, **kwargs):
        time.sleep(0.06)
        order.append("generated")
        return "# Generated instructions"

    compiler = MagicMock()
    compiler.generate_agent.side_effect = generate
    request = RepoPlanRequest(
        pack_type="project-pack",
        goal="Review repository setup.",
        repo_facts=RepoFacts(),
    )

    async def check():
        async def tick():
            await asyncio.sleep(0.01)
            order.append("tick")

        await asyncio.gather(repo_plan_claude_agent_pack(request), tick())

    with patch("api.routes.agent_packs._get_compiler", return_value=compiler):
        asyncio.run(check())

    assert order == ["tick", "generated"]


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
        "unsafe\nname.md",
        "unsafe\x00name.md",
        'unsafe"name.md',
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


@pytest.mark.parametrize("download_name", ["pack\r\nX-Bad: yes", "pack\x00name", 'pack"name'])
def test_agent_pack_manifest_rejects_unsafe_download_names(download_name: str):
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": download_name,
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


def test_agent_pack_download_rejects_header_injection_in_manifest():
    response = TestClient(app).post(
        "/agent-packs/claude/download",
        json={
            "provider": "claude",
            "pack_type": "subagent",
            "download_name": "pack\r\nX-Bad: yes",
            "preview_order": ["agents"],
            "files": [
                {
                    "path": ".claude/agents/review-agent.md",
                    "content": "hello",
                    "kind": "agents",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_agent_pack_download_encodes_non_ascii_filename_safely():
    response = TestClient(app).post(
        "/agent-packs/claude/download",
        json={
            "provider": "claude",
            "pack_type": "subagent",
            "download_name": "review-pack",
            "preview_order": ["readme"],
            "files": [
                {"path": "résumé.md", "content": "hello", "kind": "readme"},
            ],
        },
    )

    assert response.status_code == 200
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9.md" in response.headers["content-disposition"]


def test_agent_pack_manifest_canonicalizes_backslash_paths():
    manifest = AgentPackManifest.model_validate(
        {
            "provider": "claude",
            "pack_type": "subagent",
            "download_name": "demo-pack",
            "preview_order": ["agents"],
            "files": [
                {
                    "path": ".claude\\agents\\review-agent.md",
                    "content": "hello",
                    "kind": "agents",
                }
            ],
        }
    )

    assert manifest.files[0].path == ".claude/agents/review-agent.md"


def test_agent_pack_manifest_rejects_too_many_files():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents"],
                "files": [
                    {"path": f".claude/agents/{index}.md", "content": "x", "kind": "agents"}
                    for index in range(51)
                ],
            }
        )


def test_agent_pack_manifest_rejects_oversized_total_content():
    with pytest.raises(ValidationError):
        AgentPackManifest.model_validate(
            {
                "provider": "claude",
                "pack_type": "subagent",
                "download_name": "demo-pack",
                "preview_order": ["agents"],
                "files": [
                    {"path": ".claude/agents/a.md", "content": "a" * 1_000_000, "kind": "agents"},
                    {"path": ".claude/agents/b.md", "content": "b" * 1_000_000, "kind": "agents"},
                    {"path": ".claude/agents/c.md", "content": "c" * 1_000_001, "kind": "agents"},
                ],
            }
        )
