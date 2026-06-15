import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient
from app.llm_engine.example_code import SKILL_EXAMPLE_CODE_WARNING, inspect_skill_example_code
from app.llm_engine.hybrid import HybridCompiler
from api.main import app
from fastapi.testclient import TestClient


# Mock WorkerClient to avoid API calls
@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as MockClient:
        client_instance = MockClient.return_value
        # Mock generate_skill method
        client_instance.generate_skill.return_value = "# Mock Skill Definition"
        yield client_instance


def test_worker_client_generate_skill():
    # Test the generate_skill method directly (mocking the API call inside it)
    with patch("app.llm_engine.client.OpenAI") as MockOpenAI:
        mock_openai_instance = MockOpenAI.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "# Skill Definition"
        mock_openai_instance.chat.completions.create.return_value = mock_completion

        client = WorkerClient(api_key="test")
        result = client.generate_skill("Test Skill")
        assert result == "# Skill Definition"


def test_hybrid_compiler_generate_skill(mock_worker_client):
    compiler = HybridCompiler()
    # Manually inject the mock worker because HybridCompiler creates its own instance
    compiler.worker = mock_worker_client
    repo_context = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repository.",
        "highlights": ["README present"],
        "files_used": ["README.md"],
        "detected_stack": ["Python"],
    }

    result = compiler.generate_skill("Test Skill", repo_context=repo_context)
    assert result == "# Mock Skill Definition"
    mock_worker_client.generate_skill.assert_called_once()
    args, kwargs = mock_worker_client.generate_skill.call_args
    assert args == ("Test Skill",)
    assert kwargs["include_example_code"] is False
    assert kwargs["context"]["repo_context"] == {
        "source": "github_public_repo",
        "mode": "full",
        **repo_context,
    }


def test_api_generate_skill_endpoint():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock API Skill"
        repo_context = {
            "normalized_repo_url": "https://github.com/openai/openai-python",
            "repo_full_name": "openai/openai-python",
            "default_branch": "main",
            "summary": "Python SDK repository.",
            "highlights": ["README present"],
            "files_used": ["README.md"],
            "detected_stack": ["Python"],
        }

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Test Skill Request", "repo_context": repo_context},
        )

        assert response.status_code == 200
        assert response.json() == {
            "skill_definition": "# Mock API Skill",
            "example_code_requested": False,
            "example_code_present": False,
            "example_code_warning": None,
        }
        mock_compiler.generate_skill.assert_called_with(
            "Test Skill Request",
            include_example_code=False,
            repo_context={
                **repo_context,
                "summary_compact": None,
                "requested_ref": None,
                "requested_subdir": None,
            },
            repo_context_mode="full",
        )


def test_api_generate_skill_endpoint_with_example_code_enabled():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = (
            "# Mock API Skill\n\n## Implementation Example\n```python\npass\n```"
        )

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Test Skill Request", "include_example_code": True},
        )

        assert response.status_code == 200
        assert response.json() == {
            "skill_definition": "# Mock API Skill\n\n## Implementation Example\n```python\npass\n```",
            "example_code_requested": True,
            "example_code_present": True,
            "example_code_warning": None,
        }
        mock_compiler.generate_skill.assert_called_with(
            "Test Skill Request",
            include_example_code=True,
            repo_context=None,
            repo_context_mode="full",
        )


def test_api_generate_skill_endpoint_warns_when_example_code_is_missing():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock API Skill"

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Test Skill Request", "include_example_code": True},
        )

        assert response.status_code == 200
        assert response.json() == {
            "skill_definition": "# Mock API Skill",
            "example_code_requested": True,
            "example_code_present": False,
            "example_code_warning": SKILL_EXAMPLE_CODE_WARNING,
        }


def test_worker_client_omits_skill_implementation_example_when_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode, model_override=None, usage_sink=None):
            captured["messages"] = messages
            return "# Skill Definition"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_skill("Test Skill", include_example_code=False)

        assert result == "# Skill Definition"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert any(
            "Omit the entire `## Implementation Example` section" in message
            for message in system_messages
        )


def test_worker_client_requests_skill_implementation_example_when_enabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode, model_override=None, usage_sink=None):
            captured["messages"] = messages
            return "# Skill Definition"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_skill("Test Skill", include_example_code=True)

        assert result == "# Skill Definition"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert any(
            "You MUST include a final `## Implementation Example` section" in message
            for message in system_messages
        )


def test_inspect_skill_example_code_detects_valid_section():
    inspection = inspect_skill_example_code(
        "# Skill\n\n## Implementation Example\n```python\npass\n```",
        requested=True,
    )

    assert inspection.example_code_requested is True
    assert inspection.example_code_present is True
    assert inspection.example_code_warning is None


def test_inspect_skill_example_code_rejects_missing_section_even_with_fenced_code():
    inspection = inspect_skill_example_code("# Skill\n\n```python\npass\n```", requested=True)

    assert inspection.example_code_requested is True
    assert inspection.example_code_present is False
    assert inspection.example_code_warning == SKILL_EXAMPLE_CODE_WARNING


def test_inspect_skill_example_code_rejects_section_without_fenced_code():
    inspection = inspect_skill_example_code(
        "# Skill\n\n## Implementation Example\nTODO",
        requested=True,
    )

    assert inspection.example_code_requested is True
    assert inspection.example_code_present is False
    assert inspection.example_code_warning == SKILL_EXAMPLE_CODE_WARNING
