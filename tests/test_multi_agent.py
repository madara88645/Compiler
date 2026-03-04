import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient
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
    mock_worker_client.generate_agent.assert_called_with(
        "Task 1", context={}, multi_agent=False, include_example_code=False
    )

    # Test multi agent
    compiler.generate_agent("Task 2", multi_agent=True)
    mock_worker_client.generate_agent.assert_called_with(
        "Task 2", context={}, multi_agent=True, include_example_code=False
    )


def test_api_multi_agent_flag():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock Swarm"
        client = TestClient(app)

        # Test Default (False)
        client.post("/agent-generator/generate", json={"description": "Test"})
        mock_compiler.generate_agent.assert_called_with(
            "Test", multi_agent=False, include_example_code=False
        )

        # Test True
        client.post("/agent-generator/generate", json={"description": "Test", "multi_agent": True})
        mock_compiler.generate_agent.assert_called_with(
            "Test", multi_agent=True, include_example_code=False
        )


def test_worker_client_omits_swarm_example_code_when_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")
        captured = {}

        def fake_call_api(messages, max_tokens, json_mode):
            captured["messages"] = messages
            return "# Agent 1: Planner"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_agent("Test", multi_agent=True, include_example_code=False)

        assert result == "# Agent 1: Planner"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert "## Swarm Example Code (Pseudo-code Skeleton)" not in system_messages[0]
        assert any(
            "Do not add a `## Swarm Example Code` section." in message
            for message in system_messages
        )
