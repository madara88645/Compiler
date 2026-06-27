"""POST /compile RAG context retrieval is opt-in (default off) — path-leak guard."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_compile_api_no_retrieval_by_default(mock_expand, mock_search):
    mock_expand.return_value = ["login form"]
    mock_search.return_value = [{"path": "/Users/dev/private/secret.py", "snippet": "x"}]

    resp = client.post("/compile", json={"text": "make a login form", "v2": False})

    assert resp.status_code == 200
    mock_search.assert_not_called()


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_compile_api_opt_in_enables_retrieval(mock_expand, mock_search):
    mock_expand.return_value = ["login form"]
    mock_search.return_value = [{"path": "app/auth.py", "snippet": "def login(): pass"}]

    resp = client.post(
        "/compile",
        json={"text": "make a login form", "v2": False, "enable_context_retrieval": True},
    )

    assert resp.status_code == 200
    mock_search.assert_called()
