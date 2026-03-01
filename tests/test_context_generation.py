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
    compiler.context_strategist.process.return_value = {"file1.py": "content"}

    # Manually inject the mock worker
    compiler.worker = mock_worker_client

    # Test generate_agent with context
    compiler.generate_agent("Test Agent")
    compiler.context_strategist.process.assert_called_with("Test Agent")
    mock_worker_client.generate_agent.assert_called_with(
        "Test Agent", context={"file1.py": "content"}, multi_agent=False
    )

    # Test generate_skill with context
    compiler.generate_skill("Test Skill")
    compiler.context_strategist.process.assert_called_with("Test Skill")
    mock_worker_client.generate_skill.assert_called_with(
        "Test Skill", context={"file1.py": "content"}
    )


def test_api_endpoints_integration():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock API Agent"
        mock_compiler.generate_skill.return_value = "# Mock API Skill"

        client = TestClient(app)

        # Test Agent Generator Endpoint
        resp_agent = client.post("/agent-generator/generate", json={"description": "Test Agent"})
        assert resp_agent.status_code == 200
        assert resp_agent.json() == {"system_prompt": "# Mock API Agent"}

        # Test Skills Generator Endpoint
        resp_skill = client.post("/skills-generator/generate", json={"description": "Test Skill"})
        assert resp_skill.status_code == 200
        assert resp_skill.json() == {"skill_definition": "# Mock API Skill"}
