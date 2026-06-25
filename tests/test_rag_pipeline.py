from unittest.mock import patch
from app.compiler import compile_text_v2
from app.emitters import emit_system_prompt_v2


@patch("app.agents.context_strategist.search_hybrid")
@patch("app.agents.context_strategist.ContextStrategist._expand_query")
def test_compile_v2_does_not_auto_inject_rag_context(mock_expand, mock_search):
    # Setup mock return values
    mock_expand.return_value = ["login screen", "auth implementation"]
    mock_search.return_value = [
        {"path": "app/auth.py", "snippet": "def login():\n    pass"},
        {"path": "app/models.py", "snippet": "class User:\n    pass"},
    ]

    prompt = "create a login screen using auth.py"
    ir2 = compile_text_v2(prompt)

    assert "context_snippets" not in ir2.metadata
    assert "repo_context" not in ir2.metadata
    mock_expand.assert_not_called()
    mock_search.assert_not_called()

    sys_prompt = emit_system_prompt_v2(ir2)
    assert "Repo Context (ground truth)" not in sys_prompt


def test_explicit_repo_context_renders_path_safe_rag_context():
    absolute_path = "/Users/memo/project/app/auth.py"
    ir2 = compile_text_v2(
        "create a login screen using auth.py",
        repo_context={
            "source_type": "rag_index",
            "summary": {"full": "Local indexed context.", "compact": "Indexed context."},
            "files_used": [absolute_path],
            "snippets": [
                {
                    "display_path": absolute_path,
                    "content": "def login():\n    return '/Users/memo/private/.env'",
                    "source_label": "RAG index",
                }
            ],
            "budget": {"max_chars": 4000, "used_chars": 0, "truncated": False},
            "safety": {"path_safe": True, "contains_absolute_paths": False},
        },
        repo_context_mode="full",
    )

    assert "repo_context" in ir2.metadata
    sys_prompt = emit_system_prompt_v2(ir2)
    assert "## Repo Context (ground truth)" in sys_prompt
    assert "#### File: auth.py" in sys_prompt
    assert "def login():" in sys_prompt
    assert "/Users/" not in sys_prompt
    assert "[path-redacted]" in sys_prompt
