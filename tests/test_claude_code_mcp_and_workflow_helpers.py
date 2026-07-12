import json

from app.adapters.claude_code import _mcp_client_config, _workflow_scalar


def test_mcp_client_config_shape():
    config = json.loads(_mcp_client_config("my_tool"))
    assert config == {
        "mcpServers": {
            "my_tool": {"command": "python", "args": ["server.py"]},
        }
    }


def test_mcp_client_config_uses_given_tool_name_as_key():
    config = json.loads(_mcp_client_config("weather_lookup"))
    assert "weather_lookup" in config["mcpServers"]
    assert "my_tool" not in config["mcpServers"]


def test_workflow_scalar_collapses_whitespace():
    assert _workflow_scalar("line one\n  line two\ttabbed") == "line one line two tabbed"


def test_workflow_scalar_escapes_github_actions_expression_syntax():
    assert _workflow_scalar("Use ${{ secrets.TOKEN }}") == "Use $ {{ secrets.TOKEN }}"


def test_workflow_scalar_empty_string():
    assert _workflow_scalar("") == ""
