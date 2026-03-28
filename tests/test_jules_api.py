import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


def _auth_headers():
    return {"x-api-key": "test-admin-key"}


def test_jules_reply_endpoint_uses_latest_agent_message():
    activities = {
        "activities": [
            {"id": "a1", "originator": "agent", "progressUpdated": {"title": "Earlier question"}},
            {"id": "u1", "originator": "user", "progressUpdated": {"title": "Manual answer"}},
            {"id": "a2", "originator": "agent", "progressUpdated": {"title": "Latest question"}},
        ]
    }

    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls, patch("app.routers.jules.generate_jules_reply") as mock_reply:
        mock_client = mock_client_cls.return_value
        mock_client.list_activities.return_value = activities
        mock_client.get_session.return_value = {}
        mock_client.send_message.return_value = {}
        mock_reply.return_value = "Short automated answer"

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-123/reply",
            json={"instruction": "Be concise"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["reply"] == "Short automated answer"
    assert data["activity_id"] == "a2"
    mock_reply.assert_called_once()
    kwargs = mock_reply.call_args.kwargs
    assert kwargs["latest_agent_message"] == "Latest question"
    assert kwargs["instruction"] == "Be concise"
    mock_client.send_message.assert_called_once_with("session-123", "Short automated answer")


@pytest.mark.auth_required
def test_jules_sources_endpoint_requires_auth():
    client = TestClient(app)

    response = client.get("/jules/sources")

    assert response.status_code == 403


def test_jules_reply_endpoint_supports_plan_generated_activities():
    activities = {
        "activities": [
            {
                "id": "a1",
                "originator": "agent",
                "planGenerated": {
                    "plan": {
                        "steps": [
                            {
                                "title": "Summarize the repository",
                                "description": "Describe the repo in one sentence.",
                            }
                        ]
                    }
                },
            }
        ]
    }

    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls, patch("app.routers.jules.generate_jules_reply") as mock_reply:
        mock_client = mock_client_cls.return_value
        mock_client.list_activities.return_value = activities
        mock_client.get_session.return_value = {}
        mock_client.send_message.return_value = {}
        mock_reply.return_value = "This repository compiles prompts."

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-456/reply",
            json={},
            headers=_auth_headers(),
        )

    assert response.status_code == 200, response.text
    assert response.json()["latest_agent_message"] == "Summarize the repository"


def test_jules_reply_endpoint_passes_session_context_into_generation():
    activities = {
        "activities": [
            {
                "id": "a9",
                "originator": "agent",
                "progressUpdated": {"title": "What should I change?"},
            }
        ]
    }
    session_data = {
        "id": "session-789",
        "title": "Compiler smoke test",
        "prompt": "Inspect the repo and answer the current agent question.",
    }

    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls, patch("app.routers.jules.generate_jules_reply") as mock_reply:
        mock_client = mock_client_cls.return_value
        mock_client.list_activities.return_value = activities
        mock_client.get_session.return_value = session_data
        mock_client.send_message.return_value = {}
        mock_reply.return_value = "Update the prompt router."

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-789/reply",
            json={"instruction": "Answer precisely"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200, response.text
    kwargs = mock_reply.call_args.kwargs
    assert kwargs["session_title"] == "Compiler smoke test"
    assert kwargs["session_prompt"] == "Inspect the repo and answer the current agent question."


@pytest.mark.auth_required
def test_jules_reply_endpoint_requires_auth():
    client = TestClient(app)

    response = client.post("/jules/sessions/session-123/reply", json={"instruction": "Be concise"})

    assert response.status_code == 403


def test_jules_reply_endpoint_missing_agent_activity():
    activities = {
        "activities": [
            {"id": "u1", "originator": "user", "progressUpdated": {"title": "Manual answer"}},
        ]
    }

    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.list_activities.return_value = activities
        mock_client.get_session.return_value = {}

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-123/reply",
            json={"instruction": "Be concise"},
            headers=_auth_headers(),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "No agent message found in session activities."


def test_jules_reply_endpoint_client_runtime_error():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_session.side_effect = RuntimeError("Failed to connect")

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-123/reply",
            json={"instruction": "Be concise"},
            headers=_auth_headers(),
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to connect"


def test_jules_reply_endpoint_client_generic_error():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_session.side_effect = Exception("Unknown failure")

        client = TestClient(app)
        response = client.post(
            "/jules/sessions/session-123/reply",
            json={"instruction": "Be concise"},
            headers=_auth_headers(),
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to reply to Jules session."
