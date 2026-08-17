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
    mock_client.close.assert_called_once()


@pytest.mark.auth_required
def test_jules_sources_endpoint_requires_auth():
    client = TestClient(app)

    response = client.get("/jules/sources")

    assert response.status_code == 403


def test_jules_sources_endpoint_closes_client_after_success():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.list_sources.return_value = {"sources": [{"name": "sources/github/acme/repo"}]}

        client = TestClient(app)
        response = client.get("/jules/sources", headers=_auth_headers())

    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["name"] == "sources/github/acme/repo"
    mock_client.close.assert_called_once()


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
    mock_client.close.assert_called_once()


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
    assert response.json()["detail"] == "An internal error occurred."
    mock_client.close.assert_called_once()


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
    mock_client.close.assert_called_once()


def test_jules_create_session_success():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.create_session.return_value = {"id": "s-new-123"}

        client = TestClient(app)
        response = client.post(
            "/jules/sessions",
            json={
                "prompt": "build a script",
                "source": "sources/github/acme/repo",
                "automation_mode": "full",
                "title": "automated task",
                "require_plan_approval": True,
            },
            headers=_auth_headers(),
        )

        assert response.status_code == 200
        assert response.json() == {"id": "s-new-123"}
        mock_client.create_session.assert_called_once_with(
            {
                "prompt": "build a script",
                "sourceContext": {
                    "source": "sources/github/acme/repo",
                    "githubRepoContext": {"startingBranch": "main"},
                },
                "requirePlanApproval": True,
                "automationMode": "full",
                "title": "automated task",
            }
        )
        mock_client.close.assert_called_once()


def test_jules_create_session_errors():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value

        # 1. Runtime Error -> 500
        mock_client.create_session.side_effect = RuntimeError("network fail")
        client = TestClient(app)
        res1 = client.post(
            "/jules/sessions", json={"prompt": "abc", "source": "src"}, headers=_auth_headers()
        )
        assert res1.status_code == 500

        # 2. Generic Exception -> 502
        mock_client.create_session.side_effect = Exception("generic fail")
        res2 = client.post(
            "/jules/sessions", json={"prompt": "abc", "source": "src"}, headers=_auth_headers()
        )
        assert res2.status_code == 502


def test_jules_get_session_success():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_session.return_value = {"id": "s1", "title": "my title"}

        client = TestClient(app)
        response = client.get("/jules/sessions/s1", headers=_auth_headers())
        assert response.status_code == 200
        assert response.json()["title"] == "my title"
        mock_client.get_session.assert_called_once_with("s1")


def test_jules_get_session_errors():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value

        mock_client.get_session.side_effect = RuntimeError("err")
        client = TestClient(app)
        assert client.get("/jules/sessions/s1", headers=_auth_headers()).status_code == 500

        mock_client.get_session.side_effect = Exception("err")
        assert client.get("/jules/sessions/s1", headers=_auth_headers()).status_code == 502


def test_jules_get_session_activities_success():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.list_activities.return_value = {"activities": []}

        client = TestClient(app)
        response = client.get("/jules/sessions/s1/activities?page_size=40", headers=_auth_headers())
        assert response.status_code == 200
        mock_client.list_activities.assert_called_once_with("s1", page_size=40)


def test_jules_get_session_activities_errors():
    with patch.dict("os.environ", {"ADMIN_API_KEY": "test-admin-key"}, clear=False), patch(
        "app.routers.jules.JulesClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value

        mock_client.list_activities.side_effect = RuntimeError("err")
        client = TestClient(app)
        assert (
            client.get("/jules/sessions/s1/activities", headers=_auth_headers()).status_code == 500
        )

        mock_client.list_activities.side_effect = Exception("err")
        assert (
            client.get("/jules/sessions/s1/activities", headers=_auth_headers()).status_code == 502
        )


def test_generate_jules_reply_fallback_mode():
    # If OPENROUTER_API_KEY is not set, it should return context bits formatted as fallback
    from app.routers.jules import generate_jules_reply

    with patch.dict("os.environ", {}, clear=True):
        reply = generate_jules_reply(
            latest_agent_message="agent msg",
            instruction="my instruction",
            session_title="my title",
            session_prompt="my prompt",
        )
        assert "my instruction" in reply
        assert "my title" in reply
        assert "my prompt" in reply
        assert "agent msg" in reply


def test_generate_jules_reply_api_call():
    from app.routers.jules import generate_jules_reply

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch(
        "app.routers.jules.WorkerClient"
    ) as mock_worker_cls:
        mock_worker = mock_worker_cls.return_value
        mock_worker._call_api.return_value = " LLM generated reply \n"

        reply = generate_jules_reply(
            latest_agent_message="agent msg",
            instruction="my instruction",
            session_title="my title",
            session_prompt="my prompt",
        )
        assert reply == "LLM generated reply"
        mock_worker._call_api.assert_called_once()


def test_extract_activity_text_edge_cases():
    from app.routers.jules import _extract_activity_text

    # 1. progressUpdated with description only (no title)
    act1 = {"progressUpdated": {"description": "Working on it "}}
    assert _extract_activity_text(act1) == "Working on it"

    # 2. planGenerated with steps with description only (no title)
    act2 = {"planGenerated": {"plan": {"steps": [{"description": "Step 1 desc "}]}}}
    assert _extract_activity_text(act2) == "Step 1 desc"

    # 3. sessionCompleted payload with title
    act3 = {"sessionCompleted": {"title": " Done "}}
    assert _extract_activity_text(act3) == "Done"

    # 4. Empty/invalid
    assert _extract_activity_text({}) == ""
