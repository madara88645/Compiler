# Prompt Compiler MCP Server

Model Context Protocol (MCP) bridge that exposes Prompt Compiler tools to Claude Code, Claude Desktop, Cursor, and other MCP clients.

**The Prompt Compiler HTTP backend must be running before you use these tools.** Local development uses port **8080** (same as the web app and VS Code extension).

## Prerequisites

### 1. Start the backend (required)

From the repository root:

```bash
python -m uvicorn api.main:app --reload --port 8080
```

Verify it is up:

```bash
curl http://127.0.0.1:8080/health
```

### 2. Install MCP server dependencies

```bash
cd integrations/mcp-server
pip install -r requirements.txt
```

## Configuration

Environment variables (optional; align with the Chrome extension `/compile` request):

| Variable | Purpose |
|----------|---------|
| `PROMPTC_BACKEND_URL` | API origin (default `http://localhost:8080`); tools call `{origin}/compile` and related routes. |
| `PROMPTC_API_URL` | Full compile URL if set (overrides backend + `/compile`). |
| `PROMPTC_API_KEY` | Sent as `x-api-key` when the API requires optional key verification. |
| `PROMPTC_PROMPT_MODE` | `conservative` (default) or `default`; sent as `X-Prompt-Mode` and in the JSON body `mode`. |

The compile request body matches the browser extension: `v2`, `render_v2_prompts`, `diagnostics`, and `mode`.

## Claude Code

### One-line setup (`claude mcp add`)

Run from the repository root (replace the path if your clone lives elsewhere):

```bash
claude mcp add --scope project \
  --env PROMPTC_BACKEND_URL=http://127.0.0.1:8080 \
  prompt-compiler -- \
  python integrations/mcp-server/server.py
```

Inside a Claude Code session, run `/mcp` to confirm `prompt-compiler` is connected.

### Project `.mcp.json` (macOS / Linux)

Check this file into your project root so teammates get the same server. Paths use `${CLAUDE_PROJECT_DIR}` so they work on any machine:

```json
{
  "mcpServers": {
    "prompt-compiler": {
      "type": "stdio",
      "command": "python",
      "args": ["${CLAUDE_PROJECT_DIR}/integrations/mcp-server/server.py"],
      "env": {
        "PROMPTC_BACKEND_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

A copy-paste template also lives at [`.mcp.json.example`](../../.mcp.json.example) in the repo root.

### Windows `.mcp.json`

Use forward slashes or escaped backslashes in `args`:

```json
{
  "mcpServers": {
    "prompt-compiler": {
      "type": "stdio",
      "command": "python",
      "args": ["${CLAUDE_PROJECT_DIR}/integrations/mcp-server/server.py"],
      "env": {
        "PROMPTC_BACKEND_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

## Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "prompt-compiler": {
      "command": "python",
      "args": ["/absolute/path/to/Compiler/integrations/mcp-server/server.py"],
      "env": {
        "PROMPTC_BACKEND_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

Replace `/absolute/path/to/Compiler` with your clone path.

## Cursor

1. Open **Settings → Features → MCP**.
2. Click **Add New MCP Server**.
3. **Name**: `prompt-compiler`
4. **Type**: `stdio`
5. **Command**: `python /absolute/path/to/Compiler/integrations/mcp-server/server.py`
6. **Environment**: `PROMPTC_BACKEND_URL=http://127.0.0.1:8080`

## Exposed tools

| Tool | Description |
|------|-------------|
| `optimize_prompt(text)` | Returns the compiled prompt string |
| `compile_prompt(text)` | Returns the full `/compile` payload |
| `generate_agent(description, multi_agent=false)` | Returns generated agent markdown |
| `generate_skill(description)` | Returns generated skill markdown |
| `export_claude_pack(system_prompt)` | Returns a Claude Code project-pack manifest |
| `benchmark_prompt(text, model?)` | Returns the benchmark comparison payload |
| `plan_agent_pack(pack_type, goal?, risk_mode?, path?)` | Previews a repo-aware agent pack (no writes) |
| `apply_agent_pack(pack_type, goal?, risk_mode?, path?, overwrite?)` | Writes a repo-aware agent pack to disk |

## Usage

Once configured, ask your MCP client:

> "Optimize this prompt for me: write a snake game in python"

Or:

> "Generate an agent for reviewing React performance and export it as a Claude project pack."

The MCP server calls the Prompt Compiler backend on port 8080 and returns the result in the same session.

## Tests

From the repository root:

```bash
python -m pytest integrations/mcp-server/ -q
```
