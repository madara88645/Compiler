from unittest.mock import Mock

import httpx
import pytest


def test_list_sources_sends_api_key_header():
    from app.integrations.jules_client import JulesClient

    transport = Mock()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"sources": [{"name": "sources/github/acme/repo"}]}
    transport.request.return_value = response

    client = JulesClient(api_key="jules-key", transport=transport)
    data = client.list_sources()

    assert data["sources"][0]["name"] == "sources/github/acme/repo"
    transport.request.assert_called_once_with(
        "GET",
        "/v1alpha/sources",
        headers={"X-Goog-Api-Key": "jules-key"},
        json=None,
        params=None,
    )


def test_missing_api_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("JULES_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="JULES_API_KEY"):
        from app.integrations.jules_client import JulesClient

        JulesClient(api_key="")


class RecordingClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, path, *, headers=None, json=None, params=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "headers": headers,
                "json": json,
                "params": params,
            }
        )
        return self._responses.pop(0)

    def close(self):
        self.closed = True


def test_requests_reuse_persistent_http_client(monkeypatch):
    from app.integrations.jules_client import JulesClient
    import app.integrations.jules_client as jules_client_module

    recording_client = RecordingClient(
        [
            httpx.Response(200, json={"sources": [{"name": "sources/github/acme/repo"}]}),
            httpx.Response(200, json={"session": {"name": "sessions/123"}}),
        ]
    )
    created_clients = []

    def fake_client(*, base_url, timeout, transport=None):
        created_clients.append(
            {
                "base_url": base_url,
                "timeout": timeout,
                "transport": transport,
            }
        )
        return recording_client

    monkeypatch.setattr(jules_client_module.httpx, "Client", fake_client)

    client = JulesClient(api_key="jules-key", base_url="https://jules.example.com", timeout=12.5)

    sources = client.list_sources()
    session = client.create_session({"source": "sources/github/acme/repo"})

    assert len(created_clients) == 1
    assert created_clients[0] == {
        "base_url": "https://jules.example.com",
        "timeout": 12.5,
        "transport": None,
    }
    assert sources["sources"][0]["name"] == "sources/github/acme/repo"
    assert session["session"]["name"] == "sessions/123"
    assert recording_client.calls == [
        {
            "method": "GET",
            "path": "/v1alpha/sources",
            "headers": {"X-Goog-Api-Key": "jules-key"},
            "json": None,
            "params": None,
        },
        {
            "method": "POST",
            "path": "/v1alpha/sessions",
            "headers": {"X-Goog-Api-Key": "jules-key"},
            "json": {"source": "sources/github/acme/repo"},
            "params": None,
        },
    ]


def test_request_returns_empty_dict_for_empty_success_response(monkeypatch):
    from app.integrations.jules_client import JulesClient
    import app.integrations.jules_client as jules_client_module

    recording_client = RecordingClient([httpx.Response(204, content=b"")])
    monkeypatch.setattr(jules_client_module.httpx, "Client", lambda **_: recording_client)

    client = JulesClient(api_key="jules-key")

    assert client.approve_plan("session-123") == {}
    assert recording_client.calls == [
        {
            "method": "POST",
            "path": "/v1alpha/sessions/session-123:approvePlan",
            "headers": {"X-Goog-Api-Key": "jules-key"},
            "json": {},
            "params": None,
        }
    ]


def test_close_closes_underlying_http_client(monkeypatch):
    from app.integrations.jules_client import JulesClient
    import app.integrations.jules_client as jules_client_module

    recording_client = RecordingClient([])
    monkeypatch.setattr(jules_client_module.httpx, "Client", lambda **_: recording_client)

    client = JulesClient(api_key="jules-key")
    client.close()

    assert recording_client.closed is True
