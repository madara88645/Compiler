import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient
from app.llm_engine.hybrid import HybridCompiler
from api.main import app
from fastapi.testclient import TestClient


REPO_CONTEXT_FOR_RENDER = {
    "source": "github_public_repo",
    "mode": "full",
    "normalized_repo_url": "https://github.com/openai/openai-python",
    "repo_full_name": "openai/openai-python",
    "default_branch": "main",
    "summary": "Python SDK repo full summary content.",
    "summary_compact": "Python SDK repo compact summary content.",
    "highlights": ["Python package", "README present"],
    "files_used": ["README.md", "pyproject.toml"],
    "detected_stack": ["Python", "httpx"],
}


def test_context_message_renders_repo_context_as_ground_truth_block():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    message = client._context_message(
        mode="generator",
        context={"repo_context": REPO_CONTEXT_FOR_RENDER},
    )
    assert message.startswith("## Repo Context (ground truth)")
    assert "openai/openai-python" in message
    assert "Detected stack: Python, httpx" in message
    assert "Brief built from: README.md, pyproject.toml" in message
    # Full mode picks the full summary, compact summary stays out
    assert "Python SDK repo full summary content." in message
    assert "Python SDK repo compact summary content." not in message
    # repo_context is removed from runtime_context to avoid duplication
    assert "<runtime_context>" in message
    assert "repo_context" not in message.split("<runtime_context>")[1]


def test_context_message_compact_mode_uses_compact_summary():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    repo_context = {**REPO_CONTEXT_FOR_RENDER, "mode": "compact"}
    message = client._context_message(
        mode="generator",
        context={"repo_context": repo_context},
    )
    assert "Python SDK repo compact summary content." in message
    assert "Python SDK repo full summary content." not in message
    assert "### Repo brief (compact)" in message


def test_context_message_does_not_emit_mojibake():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    message = client._context_message(
        mode="generator",
        context={"repo_context": REPO_CONTEXT_FOR_RENDER},
    )

    assert "â" not in message


# Mock WorkerClient to avoid API calls
@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as MockClient:
        client_instance = MockClient.return_value
        # Mock generate_agent method
        client_instance.generate_agent.return_value = "# Mock Agent System Prompt"
        client_instance.generate_skill.return_value = "# Mock Skill Definition"
        yield client_instance


def test_worker_client_generate_methods():
    # Test generate_agent and generate_skill methods directly
    with patch("app.llm_engine.client.OpenAI") as MockOpenAI:
        mock_openai_instance = MockOpenAI.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "# Generated Content"
        mock_openai_instance.chat.completions.create.return_value = mock_completion

        client = WorkerClient(api_key="test")

        # Test generate_agent
        agent_result = client.generate_agent("Test Agent")
        assert agent_result == "# Generated Content"

        # Test generate_skill
        skill_result = client.generate_skill("Test Skill")
        assert skill_result == "# Generated Content"


def test_hybrid_compiler_context_awareness(mock_worker_client):
    compiler = HybridCompiler()
    # Mock context strategist
    compiler.context_strategist = MagicMock()
    repo_context = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repository.",
        "highlights": ["README present"],
        "files_used": ["README.md"],
        "detected_stack": ["Python"],
    }

    # Manually inject the mock worker
    compiler.worker = mock_worker_client

    # Test generate_agent with context
    compiler.generate_agent("Test Agent", repo_context=repo_context)
    compiler.context_strategist.process.assert_not_called()
    mock_worker_client.generate_agent.assert_called_with(
        "Test Agent",
        context={
            "repo_context": {
                "source_type": "github_public",
                "mode": "full",
                "repo_identity": {
                    "name": "openai/openai-python",
                    "url": "https://github.com/openai/openai-python",
                    "default_branch": "main",
                    "ref": None,
                },
                "summary": {"full": "Python SDK repository.", "compact": None},
                "detected_stack": ["Python"],
                "files_used": ["README.md"],
                "snippets": [
                    {
                        "display_path": "repo highlights",
                        "content": "README present",
                        "score": None,
                        "source_label": "GitHub brief",
                    }
                ],
                "budget": {"max_chars": 4000, "used_chars": 0, "truncated": False},
                "safety": {"path_safe": True, "contains_absolute_paths": False},
            },
        },
        multi_agent=False,
        include_example_code=False,
    )

    # Test generate_skill with context
    compiler.generate_skill("Test Skill", repo_context=repo_context)
    compiler.context_strategist.process.assert_not_called()
    mock_worker_client.generate_skill.assert_called_with(
        "Test Skill",
        context={
            "repo_context": {
                "source_type": "github_public",
                "mode": "full",
                "repo_identity": {
                    "name": "openai/openai-python",
                    "url": "https://github.com/openai/openai-python",
                    "default_branch": "main",
                    "ref": None,
                },
                "summary": {"full": "Python SDK repository.", "compact": None},
                "detected_stack": ["Python"],
                "files_used": ["README.md"],
                "snippets": [
                    {
                        "display_path": "repo highlights",
                        "content": "README present",
                        "score": None,
                        "source_label": "GitHub brief",
                    }
                ],
                "budget": {"max_chars": 4000, "used_chars": 0, "truncated": False},
                "safety": {"path_safe": True, "contains_absolute_paths": False},
            },
        },
        include_example_code=False,
    )

    # Test compact mode threads through to the merged context.
    mock_worker_client.generate_agent.reset_mock()
    compiler.generate_agent("Test Agent", repo_context=repo_context, repo_context_mode="compact")
    _, agent_kwargs = mock_worker_client.generate_agent.call_args
    assert agent_kwargs["context"]["repo_context"]["mode"] == "compact"


def test_api_endpoints_integration():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock API Agent"
        mock_compiler.generate_skill.return_value = "# Mock API Skill"
        mock_compiler.analyze_public_github_repo.return_value = None

        client = TestClient(app)
        repo_context = {
            "normalized_repo_url": "https://github.com/openai/openai-python",
            "repo_full_name": "openai/openai-python",
            "default_branch": "main",
            "summary": "Python SDK repository.",
            "highlights": ["README present"],
            "files_used": ["README.md"],
            "detected_stack": ["Python"],
        }

        # Pydantic adds the optional fields on round-trip (summary_compact, requested_ref, requested_subdir)
        normalized_repo_context = {
            **repo_context,
            "summary_compact": None,
            "requested_ref": None,
            "requested_subdir": None,
        }

        # Test Agent Generator Endpoint
        resp_agent = client.post(
            "/agent-generator/generate",
            json={"description": "Test Agent", "repo_context": repo_context},
        )
        assert resp_agent.status_code == 200
        assert resp_agent.json() == {
            "system_prompt": "# Mock API Agent",
            "example_code_requested": False,
            "example_code_present": False,
            "example_code_warning": None,
        }
        mock_compiler.generate_agent.assert_called_with(
            "Test Agent",
            multi_agent=False,
            include_example_code=False,
            repo_context=normalized_repo_context,
            repo_context_mode="full",
        )

        # Test Skills Generator Endpoint, exercising compact mode through the API
        resp_skill = client.post(
            "/skills-generator/generate",
            json={
                "description": "Test Skill",
                "repo_context": repo_context,
                "repo_context_mode": "compact",
            },
        )
        assert resp_skill.status_code == 200
        assert resp_skill.json() == {
            "skill_definition": "# Mock API Skill",
            "example_code_requested": False,
            "example_code_present": False,
            "example_code_warning": None,
        }
        mock_compiler.generate_skill.assert_called_with(
            "Test Skill",
            include_example_code=False,
            repo_context=normalized_repo_context,
            repo_context_mode="compact",
        )
