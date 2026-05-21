import os
import tempfile
from unittest.mock import MagicMock, patch

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
def test_generator_endpoints_work_without_api_key():
    client = TestClient(app)

    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock API Agent"
        mock_compiler.generate_skill.return_value = "# Mock API Skill"

        agent_resp = client.post("/agent-generator/generate", json={"description": "Test Agent"})
        skill_resp = client.post("/skills-generator/generate", json={"description": "Test Skill"})

    assert agent_resp.status_code == 200
    assert agent_resp.json() == {"system_prompt": "# Mock API Agent"}
    assert skill_resp.status_code == 200
    assert skill_resp.json() == {"skill_definition": "# Mock API Skill"}


@pytest.mark.auth_required
def test_rag_upload_works_without_api_key(monkeypatch):
    """RAG upload uses optional auth — requests without a key should succeed."""
    import os
    import tempfile

    client = TestClient(app)

    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr("app.rag.simple_index.DEFAULT_DB_PATH", os.path.join(td, "index.db"))
        monkeypatch.setenv("PROMPTC_UPLOAD_DIR", os.path.join(td, "uploads"))

        response = client.post(
            "/rag/upload",
            json={"filename": "auth.py", "content": "def login():\n    return True"},
        )

    assert response.status_code == 200


@pytest.mark.auth_required
def test_optimize_works_without_api_key():
    client = TestClient(app)

    with patch("api.main.get_compiler") as mock_get_compiler:
        mock_get_compiler.return_value.worker.optimize_prompt.return_value = ("short prompt", None)

        response = client.post("/optimize", json={"text": "a much longer prompt"})

    assert response.status_code == 200


@pytest.mark.auth_required
def test_public_routes_rate_limited_by_ip(monkeypatch):
    """A burst from a single IP hits 429 after 20 heavy requests in 60s."""
    monkeypatch.setattr("api.auth.PUBLIC_HEAVY_RATE_LIMIT", 3)
    client = TestClient(app)

    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir.model_dump.return_value = {}
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"
        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        for _ in range(3):
            assert client.post("/compile/fast", json={"text": "h"}).status_code == 200
        assert client.post("/compile/fast", json={"text": "h"}).status_code == 429


@pytest.mark.auth_required
def test_per_ip_buckets_isolated(monkeypatch):
    """Two different X-Forwarded-For headers get separate buckets."""
    monkeypatch.setattr("api.auth.PUBLIC_HEAVY_RATE_LIMIT", 1)
    client = TestClient(app)

    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir.model_dump.return_value = {}
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"
        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        assert (
            client.post(
                "/compile/fast",
                json={"text": "h"},
                headers={"X-Forwarded-For": "1.1.1.1"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/compile/fast",
                json={"text": "h"},
                headers={"X-Forwarded-For": "1.1.1.1"},
            ).status_code
            == 429
        )
        assert (
            client.post(
                "/compile/fast",
                json={"text": "h"},
                headers={"X-Forwarded-For": "2.2.2.2"},
            ).status_code
            == 200
        )


@pytest.mark.auth_required
def test_repo_context_endpoint_uses_heavy_public_rate_limit(monkeypatch):
    monkeypatch.setattr("api.auth.PUBLIC_HEAVY_RATE_LIMIT", 1)
    client = TestClient(app)
    payload = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repo summary.",
        "highlights": ["Python package"],
        "files_used": ["README.md"],
        "detected_stack": ["Python"],
    }

    with patch("api.routes.generators.analyze_public_github_repo", return_value=payload):
        first = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        second = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )

    assert first.status_code == 200
    assert second.status_code == 429


@pytest.mark.auth_required
def test_repo_context_endpoint_keeps_per_ip_buckets_isolated(monkeypatch):
    monkeypatch.setattr("api.auth.PUBLIC_HEAVY_RATE_LIMIT", 1)
    client = TestClient(app)
    payload = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repo summary.",
        "highlights": ["Python package"],
        "files_used": ["README.md"],
        "detected_stack": ["Python"],
    }

    with patch("api.routes.generators.analyze_public_github_repo", return_value=payload):
        first = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        second = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        third = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
            headers={"X-Forwarded-For": "2.2.2.2"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert third.status_code == 200


@pytest.mark.auth_required
def test_benchmark_works_without_api_key():
    client = TestClient(app)

    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
        mock_llm.side_effect = ["raw output", "compiled output"]
        response = client.post(
            "/benchmark/run",
            json={"text": "Explain Python", "model": "llama-3.1-8b-instant"},
        )

    assert response.status_code == 200


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
        assert "invalid path specified" in response.json()["detail"].lower()


def test_cors_preflight_allows_prompt_mode_header():
    client = TestClient(app)

    response = client.options(
        "/compile",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Prompt-Mode",
        },
    )

    assert response.status_code == 200
    assert "x-prompt-mode" in response.headers["access-control-allow-headers"].lower()


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
