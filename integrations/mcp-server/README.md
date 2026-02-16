# myCompiler MCP Server

This directory contains a Model Context Protocol (MCP) server integration for `myCompiler`.
It exposes `myCompiler` tools (like `optimize_prompt`) to MCP clients such as Claude Desktop and Cursor.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Start the API Server**:
    Ensure the main `myCompiler` API is running:
    ```bash
    # From project root
    uvicorn api.main:app --port 8000
    ```

## Configuration

### Claude Desktop

Add the following to your `claude_desktop_config.json` (usually in `%APPDATA%\Claude\` on Windows or `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "myCompiler": {
      "command": "python",
      "args": [
        "C:\\Users\\User\\Desktop\\myCompiler\\integrations\\mcp-server\\server.py"
      ]
    }
  }
}
```

> **Note**: Verify the path to `server.py`.

### Cursor

1.  Go to **Settings > Features > MCP**.
2.  Click **Add New MCP Server**.
3.  **Name**: `myCompiler`
4.  **Type**: `stdio`
5.  **Command**: `python C:\Users\User\Desktop\myCompiler\integrations\mcp-server\server.py`

## Usage

Once configured, you can ask Claude or Cursor:
> "Optimize this prompt for me: 'write a snake game in python'"

The tool `optimize_prompt` will be called, and the optimized system prompt from `myCompiler` will be returned.
