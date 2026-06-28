from unittest.mock import patch
from app.compiler import compile_text_v2
from app.emitters import emit_system_prompt_v2


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_rag_integration_in_compiler(mock_expand, mock_search):
    # Setup mock return values
    mock_expand.return_value = ["login screen", "auth implementation"]
    mock_search.return_value = [
        {"path": "app/auth.py", "snippet": "def login():\n    pass"},
        {"path": "app/models.py", "snippet": "class User:\n    pass"},
    ]

    # Run compiler with a prompt that "should" trigger retrieval (opt-in)
    prompt = "create a login screen using auth.py"
    ir2 = compile_text_v2(prompt, enable_context_retrieval=True)

    # 1. Assert Strategy Agent fetched context
    assert "context_snippets" in ir2.metadata
    assert len(ir2.metadata["context_snippets"]) == 2
    assert ir2.metadata["context_snippets"][0]["path"] == "app/auth.py"

    # 2. Assert Diagnostics alerted the user
    # Find the 'context' category diagnostic
    diag = next((d for d in ir2.diagnostics if d.category == "context"), None)
    assert diag is not None
    assert "Strategist retrieved 2 relevant sources" in diag.message

    # 3. Assert System Prompt includes the snippets
    sys_prompt = emit_system_prompt_v2(ir2)
    assert "### Context (Code & Knowledge)" in sys_prompt
    assert "#### File: app/auth.py" in sys_prompt
    assert "def login():" in sys_prompt


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_rag_disabled_by_default_no_context_leak(mock_expand, mock_search):
    """Default compile must NOT retrieve local RAG context (path-leak guard)."""
    mock_expand.return_value = ["login form"]
    mock_search.return_value = [
        {"path": "/Users/dev/private/secret_local_file.py", "snippet": "TOKEN = 'leak'"},
    ]

    ir2 = compile_text_v2("create a login screen using auth.py")

    # Strategist never queried the local index
    mock_search.assert_not_called()
    # No snippets injected into IR metadata
    assert "context_snippets" not in ir2.metadata
    # System Prompt has no Context section and no leaked local path
    sys_prompt = emit_system_prompt_v2(ir2)
    assert "### Context (Code & Knowledge)" not in sys_prompt
    assert "secret_local_file.py" not in sys_prompt
