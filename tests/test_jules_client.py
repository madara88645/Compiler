from unittest.mock import Mock

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
