import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient
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

    result = compiler.generate_skill("Test Skill")
    assert result == "# Mock Skill Definition"
    # HybridCompiler now injects context, so we expect the context argument
    # We can use ANY for the context content since it depends on the mock vector db
    from unittest.mock import ANY

    mock_worker_client.generate_skill.assert_called_with("Test Skill", context=ANY)


def test_api_generate_skill_endpoint():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock API Skill"

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate", json={"description": "Test Skill Request"}
        )

        assert response.status_code == 200
        assert response.json() == {"skill_definition": "# Mock API Skill"}
        mock_compiler.generate_skill.assert_called_with("Test Skill Request")
