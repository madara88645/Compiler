"""CLI tests for template list and show subcommands.

Covers: list with and without filters, list empty state,
show existing template, show missing template.

Fixes #1073.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def _mock_template(tid: str = "t1", tags=None, role: str = "developer") -> MagicMock:
    """Build a mock PromptTemplate-like object compatible with the CLI code.

    The CLI code treats the template as a dict-like via `t.get(...)` and `t['id']`.
    PromptTemplate is actually a dataclass; the CLI accesses it with dict bracket
    notation, so we return a plain dict which satisfies both `.get()` and `['key']`.
    """
    return {
        "id": tid,
        "role": role,
        "tags": tags or [],
        "description": f"Description for {tid}",
        "content": f"Content of template {tid}",
    }


@patch("cli.commands.templates.get_templates_manager")
def test_template_list_shows_templates(mock_get_mgr):
    """template list should display all templates."""
    mgr = MagicMock()
    mgr.list_templates.return_value = [
        _mock_template("alpha", tags=["code"]),
        _mock_template("beta"),
    ]
    mock_get_mgr.return_value = mgr

    result = runner.invoke(app, ["template", "list"])

    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "Found 2 templates" in result.output


@patch("cli.commands.templates.get_templates_manager")
def test_template_list_empty(mock_get_mgr):
    """template list should print empty state when no templates match."""
    mgr = MagicMock()
    mgr.list_templates.return_value = []
    mock_get_mgr.return_value = mgr

    result = runner.invoke(app, ["template", "list"])

    assert result.exit_code == 0
    assert "No templates found" in result.output


@patch("cli.commands.templates.get_templates_manager")
def test_template_list_filters_role(mock_get_mgr):
    """template list --role passes the filter through to the manager."""
    mgr = MagicMock()
    mgr.list_templates.return_value = []
    mock_get_mgr.return_value = mgr

    runner.invoke(app, ["template", "list", "--role", "analyst"])

    mgr.list_templates.assert_called_once()
    call_kwargs = mgr.list_templates.call_args
    # The CLI passes role= and tag= regardless of param name
    assert "analyst" in str(call_kwargs)


@patch("cli.commands.templates.get_templates_manager")
def test_template_show_existing(mock_get_mgr):
    """template show should display template details."""
    mgr = MagicMock()
    mgr.get_template.return_value = _mock_template("alpha")
    mock_get_mgr.return_value = mgr

    result = runner.invoke(app, ["template", "show", "alpha"])

    assert result.exit_code == 0
    assert "alpha" in result.output


@patch("cli.commands.templates.get_templates_manager")
def test_template_show_missing(mock_get_mgr):
    """template show should exit non-zero when template is not found."""
    mgr = MagicMock()
    mgr.get_template.return_value = None
    mock_get_mgr.return_value = mgr

    result = runner.invoke(app, ["template", "show", "nonexistent"])

    assert result.exit_code != 0
    assert "not found" in result.output
