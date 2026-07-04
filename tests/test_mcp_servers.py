from __future__ import annotations

import json

from app.adapters.mcp_servers import (
    MCP_SERVER_REGISTRY,
    render_mcp_json,
    unregistered_servers,
)


def test_render_none_for_empty():
    assert render_mcp_json([]) is None


def test_render_none_for_unregistered_only():
    assert render_mcp_json(["figma", "jira"]) is None


def test_render_github_slack_secret_safe():
    payload = json.loads(render_mcp_json(["github", "slack"]))
    servers = payload["mcpServers"]
    assert servers["github"]["type"] == "http"
    assert servers["github"]["url"] == "https://api.githubcopilot.com/mcp/"
    assert servers["slack"]["url"] == "https://mcp.slack.com/mcp"
    # github's secret is an env placeholder, not a literal token
    assert servers["github"]["headers"]["Authorization"].startswith("Bearer ${")
    # slack (OAuth) carries no headers/env
    assert "headers" not in servers["slack"]
    assert "env" not in servers["slack"]
    # No literal secret anywhere: every headers/env value is a ${...} expansion
    for cfg in servers.values():
        for section in ("headers", "env"):
            for value in cfg.get(section, {}).values():
                assert "${" in value


def test_render_omits_unregistered():
    payload = json.loads(render_mcp_json(["github", "figma"]))
    assert "github" in payload["mcpServers"]
    assert "figma" not in payload["mcpServers"]


def test_registry_has_no_archived_npx_packages():
    # Guard against re-introducing the archived @modelcontextprotocol/server-* stubs.
    blob = json.dumps(MCP_SERVER_REGISTRY)
    assert "@modelcontextprotocol/server-" not in blob


def test_unregistered_servers():
    assert unregistered_servers(["github", "figma", "jira"]) == ["figma", "jira"]
    assert unregistered_servers(["github", "slack"]) == []
