import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import APIKey, SessionLocal
from app.llm_engine.client import WorkerClient


@pytest.fixture
def test_key():
    db = SessionLocal()
    key = APIKey(key="sk_test_hardening", owner="pytest")
    db.add(key)
    try:
        db.commit()
    except Exception:
        db.rollback()

    yield "sk_test_hardening"

    db.delete(key)
    db.commit()
    db.close()


@pytest.mark.auth_required
def test_generator_endpoints_require_api_key():
    client = TestClient(app)

    agent_resp = client.post("/agent-generator/generate", json={"description": "Test Agent"})
    skill_resp = client.post("/skills-generator/generate", json={"description": "Test Skill"})

    assert agent_resp.status_code == 403
    assert skill_resp.status_code == 403


@pytest.mark.auth_required
def test_rag_upload_requires_api_key():
    client = TestClient(app)

    response = client.post(
        "/rag/upload",
        json={"filename": "auth.py", "content": "def login():\n    return True"},
    )

    assert response.status_code == 403


@pytest.mark.auth_required
def test_rag_upload_indexes_and_searches_content(test_key, monkeypatch):
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr("app.rag.simple_index.DEFAULT_DB_PATH", os.path.join(td, "index.db"))
        monkeypatch.setenv("PROMPTC_UPLOAD_DIR", os.path.join(td, "uploads"))

        upload = client.post(
            "/rag/upload",
            headers={"x-api-key": test_key},
            json={
                "filename": "calculator.py",
                "content": "def add(a, b):\n    return a + b\n\ndef multiply(x, y):\n    return x * y",
            },
        )

        assert upload.status_code == 200, upload.text
        payload = upload.json()
        assert payload["ingested_docs"] == 1
        assert payload["total_chunks"] >= 1
        assert payload["filename"] == "calculator.py"

        search = client.post("/rag/search", json={"query": "multiply", "limit": 3})
        assert search.status_code == 200, search.text
        results = search.json()
        assert results
        assert any("multiply" in item["snippet"].lower() for item in results)
        assert all(set(item.keys()) >= {"path", "snippet", "score"} for item in results)


@pytest.mark.auth_required
def test_rag_ingest_rejects_path_outside_allowed_root(test_key, monkeypatch):
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as td:
        inside = os.path.join(td, "inside")
        outside = os.path.join(td, "outside")
        os.makedirs(inside, exist_ok=True)
        os.makedirs(outside, exist_ok=True)

        allowed_file = os.path.join(inside, "allowed.txt")
        blocked_file = os.path.join(outside, "blocked.txt")
        with open(allowed_file, "w", encoding="utf-8") as handle:
            handle.write("allowed content")
        with open(blocked_file, "w", encoding="utf-8") as handle:
            handle.write("blocked content")

        monkeypatch.setenv("PROMPTC_RAG_ALLOWED_ROOTS", inside)

        response = client.post(
            "/rag/ingest",
            headers={"x-api-key": test_key},
            json={"paths": [blocked_file]},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Path security check failed."


def test_worker_client_wraps_user_input_and_context_with_tags():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode=True):
            captured["messages"] = messages
            return '{"ir":{"language":"en","persona":"assistant","role":"helper","domain":"general","intents":[],"goals":[],"tasks":[],"inputs":{},"constraints":[],"style":[],"tone":[],"output_format":"text","length_hint":"medium","steps":[],"examples":[],"banned":[],"tools":[],"metadata":{}},"system_prompt":"sys","user_prompt":"usr","plan":"1. step","optimized_content":"expanded","diagnostics":[],"thought_process":"ok"}'

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            client.process("user says hello", context={"retrieval_status": "empty"})

        user_messages = [msg["content"] for msg in captured["messages"] if msg["role"] == "user"]
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]

        assert any(
            "<user_input>" in message and "</user_input>" in message for message in user_messages
        )
        assert any(
            "<runtime_context>" in message and "</runtime_context>" in message
            for message in system_messages
        )
