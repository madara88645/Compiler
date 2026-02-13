import pytest
from unittest.mock import MagicMock
from app.optimizer.critic import CriticAgent, CriticVerdict


@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mock the _call_api method to return a valid JSON string
    return client


def test_critic_initialization():
    agent = CriticAgent()
    assert agent.client is not None
    assert "You are Agent 7" in agent.prompt_template


def test_critique_accept(mock_client):
    # Setup mock response
    valid_response = {"verdict": "ACCEPT", "score": 95, "issues": [], "feedback": None}
    mock_client._call_api.return_value = (
        str(valid_response).replace("'", '"').replace("None", "null")
    )

    agent = CriticAgent(client=mock_client)
    result = agent.critique(
        user_request="Print hello world",
        system_prompt="You are a python assistant",
        generated_code="print('hello world')",
        context="",
    )

    assert isinstance(result, CriticVerdict)
    assert result.verdict == "ACCEPT"
    assert result.score == 95
    assert len(result.issues) == 0


def test_critique_reject_hallucination(mock_client):
    # Setup mock response for rejection
    reject_response = {
        "verdict": "REJECT",
        "score": 40,
        "issues": [
            {
                "type": "Hallucination",
                "description": "Function auth.verifyUser() does not exist.",
                "severity": "critical",
            }
        ],
        "feedback": "Use auth.check_user() instead.",
    }
    mock_client._call_api.return_value = str(reject_response).replace("'", '"')

    agent = CriticAgent(client=mock_client)
    result = agent.critique(
        user_request="Verify user",
        system_prompt="...",
        generated_code="auth.verifyUser()",
        context="auth.ts contains check_user()",
    )

    assert result.verdict == "REJECT"
    assert result.score == 40
    assert len(result.issues) == 1
    assert result.issues[0].type == "Hallucination"
    assert "auth.verifyUser" in result.issues[0].description


def test_critique_parsing_error(mock_client):
    # Setup mock with invalid JSON
    mock_client._call_api.return_value = "Not JSON"

    agent = CriticAgent(client=mock_client)
    result = agent.critique("req", "sys", "code", "ctx")

    assert result.verdict == "REJECT"
    assert result.score == 0
    assert result.issues[0].type == "System Error"
