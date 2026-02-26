import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.hybrid import HybridCompiler
from api.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as MockClient:
        client_instance = MockClient.return_value
        client_instance.generate_agent.return_value = "# Mock Agent Output"
        yield client_instance


def test_hybrid_compiler_multi_agent(mock_worker_client):
    compiler = HybridCompiler()
    compiler.worker = mock_worker_client
    # Mock context strategist
    compiler.context_strategist = MagicMock()
    compiler.context_strategist.process.return_value = {}

    # Test single agent
    compiler.generate_agent("Task 1", multi_agent=False)
    mock_worker_client.generate_agent.assert_called_with("Task 1", context={}, multi_agent=False)

    # Test multi agent
    compiler.generate_agent("Task 2", multi_agent=True)
    mock_worker_client.generate_agent.assert_called_with("Task 2", context={}, multi_agent=True)


def test_api_multi_agent_flag():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock Swarm"
        client = TestClient(app)

        # Test Default (False)
        client.post("/agent-generator/generate", json={"description": "Test"})
        mock_compiler.generate_agent.assert_called_with("Test", multi_agent=False)

        # Test True
        client.post("/agent-generator/generate", json={"description": "Test", "multi_agent": True})
        mock_compiler.generate_agent.assert_called_with("Test", multi_agent=True)
