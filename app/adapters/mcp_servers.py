"""Known MCP server config stubs for generated agent packs.

Configs verified 2026-07-04 against https://code.claude.com/docs/en/mcp.
The old @modelcontextprotocol/server-* npx packages are archived; the current
GitHub/Slack/Notion/Sentry servers are remote HTTP. `figma` and `jira` are
intentionally absent (no current config confirmed) and are surfaced in the
pack README instead. Secrets are only ${ENV} placeholders or OAuth (no secret).
"""

from __future__ import annotations

import json

MCP_SERVER_REGISTRY: dict[str, dict] = {
    "github": {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer ${GITHUB_PAT}"},
    },
    "slack": {"type": "http", "url": "https://mcp.slack.com/mcp"},
    "notion": {"type": "http", "url": "https://mcp.notion.com/mcp"},
    "sentry": {"type": "http", "url": "https://mcp.sentry.dev/mcp"},
}


def render_mcp_json(server_names: list[str]) -> str | None:
    """Render a .mcp.json for the registered servers among ``server_names``.

    Returns None when none of the names are registered. Registry order is used
    for deterministic output; unregistered names are ignored.
    """
    selected = {
        name: config
        for name, config in MCP_SERVER_REGISTRY.items()
        if name in server_names
    }
    if not selected:
        return None
    return json.dumps({"mcpServers": selected}, indent=2)


def unregistered_servers(server_names: list[str]) -> list[str]:
    """Detected server names that have no verified registry config."""
    return [name for name in server_names if name not in MCP_SERVER_REGISTRY]
