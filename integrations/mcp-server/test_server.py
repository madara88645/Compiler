import asyncio
from unittest.mock import patch

import pytest

import server


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = "ok"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _MockAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.responses = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def test_compile_prompt_posts_to_compile_endpoint(monkeypatch: pytest.MonkeyPatch):
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse(
            {
                "expanded_prompt_v2": "compiled output",
                "policy": {"risk_level": "low"},
            }
        )
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.compile_prompt("write a safer deploy script"))

    assert result["expanded_prompt_v2"] == "compiled output"
    assert client.calls[0]["url"] == "https://api.example/compile"
    assert client.calls[0]["json"]["text"] == "write a safer deploy script"


def test_generate_agent_posts_to_generator_endpoint(monkeypatch: pytest.MonkeyPatch):
    client = _MockAsyncClient()
    client.responses.append(_MockResponse({"system_prompt": "# Agent"}))

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.generate_agent("Review React performance"))

    assert result == "# Agent"
    assert client.calls[0]["url"] == "https://api.example/agent-generator/generate"
    assert client.calls[0]["json"]["description"] == "Review React performance"


def test_generate_skill_posts_to_generator_endpoint(monkeypatch: pytest.MonkeyPatch):
    client = _MockAsyncClient()
    client.responses.append(_MockResponse({"skill_definition": "# Skill"}))

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.generate_skill("Fetch and summarize docs"))

    assert result == "# Skill"
    assert client.calls[0]["url"] == "https://api.example/skills-generator/generate"
    assert client.calls[0]["json"]["description"] == "Fetch and summarize docs"


def test_export_claude_pack_posts_to_export_endpoint(monkeypatch: pytest.MonkeyPatch):
    client = _MockAsyncClient()
    client.responses.append(_MockResponse({"files": [{"path": "CLAUDE.md", "content": "..."}]}))

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.export_claude_pack("# Agent"))

    assert result["files"][0]["path"] == "CLAUDE.md"
    assert client.calls[0]["url"] == "https://api.example/agent-generator/export"
    assert client.calls[0]["json"]["format"] == "claude-project-pack"


def test_benchmark_prompt_posts_to_benchmark_endpoint(monkeypatch: pytest.MonkeyPatch):
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse(
            {
                "winner": "compiled",
                "improvement_score": 25.0,
                "raw_output": "raw",
                "compiled_output": "compiled",
                "compiled_prompt": "prompt",
            }
        )
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.benchmark_prompt("Explain RAG"))

    assert result["winner"] == "compiled"
    assert client.calls[0]["url"] == "https://api.example/benchmark/run"
    assert client.calls[0]["json"]["text"] == "Explain RAG"


def test_plan_agent_pack_posts_repo_facts(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    client = _MockAsyncClient()
    client.responses.append(_MockResponse({"manifest": {"files": []}, "plan": [], "detected": {}}))

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.plan_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    assert client.calls[0]["url"] == "https://api.example/agent-packs/claude/repo-plan"
    body = client.calls[0]["json"]
    assert "package.json" in body["repo_facts"]["files"]
    assert body["pack_type"] == "project-pack"
    assert "plan" in result


def test_apply_agent_pack_writes_files(tmp_path, monkeypatch: pytest.MonkeyPatch):
    manifest = {"files": [{"path": "CLAUDE.md", "content": "NEW"}]}
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse({"manifest": manifest, "plan": [{"path": "CLAUDE.md", "action": "create"}]})
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.apply_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    assert (tmp_path / "CLAUDE.md").read_text() == "NEW"
    assert result["written"]["created"] == ["CLAUDE.md"]


def test_apply_agent_pack_merges_claude_md_in_place(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "CLAUDE.md").write_text("# Existing\n\n## Setup\nrun make\n")
    merged = "# Existing\n\n## Setup\nrun make\n\n<!-- marker -->\n\n## Deploy\nship\n"
    manifest = {"files": [{"path": "CLAUDE.md", "content": merged}]}
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse({"manifest": manifest, "plan": [{"path": "CLAUDE.md", "action": "merge"}]})
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        result = asyncio.run(server.apply_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    assert (tmp_path / "CLAUDE.md").read_text() == merged  # written in place
    assert not (tmp_path / "CLAUDE.md.new").exists()  # not a .new conflict
    assert result["written"]["overwritten"] == ["CLAUDE.md"]


def test_apply_agent_pack_non_merge_conflict_still_new(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "README.md").write_text("old")
    manifest = {"files": [{"path": "README.md", "content": "new"}]}
    client = _MockAsyncClient()
    client.responses.append(
        _MockResponse(
            {"manifest": manifest, "plan": [{"path": "README.md", "action": "overwrite"}]}
        )
    )

    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://api.example")
    with patch("server.httpx.AsyncClient", return_value=client):
        asyncio.run(server.apply_agent_pack("project-pack", goal="x", path=str(tmp_path)))

    # An "overwrite"-action file the caller did NOT confirm still lands as .new (no-clobber).
    assert (tmp_path / "README.md").read_text() == "old"
    assert (tmp_path / "README.md.new").read_text() == "new"
