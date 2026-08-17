"""CLI `compile` RAG context retrieval is opt-in (default off) — path-leak guard."""
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app as _app

_runner = CliRunner()


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_cli_compile_does_not_retrieve_by_default(mock_expand, mock_search):
    mock_expand.return_value = ["login form"]
    mock_search.return_value = [{"path": "/Users/dev/private/secret.py", "snippet": "x"}]

    result = _runner.invoke(_app, ["compile", "make a login form", "--json-only"])

    assert result.exit_code == 0, result.output
    # Local RAG index must NOT be queried unless explicitly enabled.
    mock_search.assert_not_called()
    assert "secret.py" not in result.output


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_cli_compile_rag_flag_enables_retrieval(mock_expand, mock_search):
    mock_expand.return_value = ["login form"]
    mock_search.return_value = [{"path": "app/auth.py", "snippet": "def login(): pass"}]

    result = _runner.invoke(_app, ["compile", "make a login form", "--rag", "--json-only"])

    assert result.exit_code == 0, result.output
    mock_search.assert_called()
