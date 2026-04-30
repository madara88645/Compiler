from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import MagicMock, patch
from fastapi import Request
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app
from api.auth import APIKey, SessionLocal, verify_api_key
from app.compiler import compile_text_v2
from app.rag import simple_index

client = TestClient(app)


# Mock DB or insert test key
@pytest.fixture
def test_key():
    db = SessionLocal()
    key = APIKey(key="sk_test_123", owner="pytest")
    db.add(key)
    try:
        db.commit()
    except Exception:
        db.rollback()

    yield "sk_test_123"

    # Cleanup
    db.delete(key)
    db.commit()
    db.close()


def test_compile_fast_no_key():
    resp = client.post("/compile/fast", json={"text": "hello"})
    assert resp.status_code == 403


def test_compile_fast_invalid_key():
    resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": "invalid"})
    assert resp.status_code == 403


def test_compile_fast_success(test_key):
    # Mock hybrid_compiler to avoid actual LLM calls
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir.model_dump.return_value = {}
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"

        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": test_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["heuristic_version"] == "v2-fast"
        assert "processing_ms" in data


def test_compile_fast_trivial_input_forces_instruction_prompt(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        ir2 = compile_text_v2("merhaba", offline_only=True)
        mock_res = MagicMock()
        mock_res.ir = ir2
        mock_res.system_prompt = "Sen yardimci bir asistansin."
        mock_res.user_prompt = "Merhaba! Nasil yardimci olabilirim?"
        mock_res.plan = "1. Selam ver"
        mock_res.optimized_content = "Merhaba! Nasil yardimci olabilirim?"

        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        resp = client.post(
            "/compile/fast",
            json={"text": "merhaba", "mode": "conservative"},
            headers={"x-api-key": test_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "kullanici mesaji" in data["expanded_prompt_v2"].lower()
        assert "yardimci olabilirim" not in data["expanded_prompt_v2"].lower()


def test_compile_fast_internal_error(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.cache = {}
        mock_compiler.worker.process.side_effect = Exception("Test Internal Error")

        resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": test_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ir_v2"]["policy"]["risk_level"] == "low"
        assert data["expanded_prompt_v2"]
        assert any(
            item["category"] == "system" and item["severity"] == "warning"
            for item in data["ir_v2"]["diagnostics"]
        )


def test_compile_fast_none_worker_result_falls_back(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.cache = {}
        mock_compiler.worker.process.return_value = None

        resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": test_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ir_v2"]["policy"]["risk_level"] == "low"
        assert data["system_prompt_v2"]
        assert data["user_prompt_v2"]
        assert data["plan_v2"]
        assert data["expanded_prompt_v2"]


def test_compile_fast_empty_ir_dump_gets_policy_defaults(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir.model_dump.return_value = {}
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"
        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        resp = client.post("/compile/fast", json={"text": "hello"}, headers={"x-api-key": test_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ir_v2"]["policy"]["risk_level"] == "low"
        assert data["ir"]["policy"]["execution_mode"]


def test_compile_fast_blank_prompt_parts_are_generated(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir = compile_text_v2("Summarize this incident report.", offline_only=True)
        mock_res.system_prompt = ""
        mock_res.user_prompt = ""
        mock_res.plan = ""
        mock_res.optimized_content = ""
        mock_compiler.worker.process.return_value = mock_res
        mock_compiler.cache = {}

        resp = client.post(
            "/compile/fast",
            json={"text": "Summarize this incident report.", "mode": "default"},
            headers={"x-api-key": test_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_prompt_v2"]
        assert data["user_prompt_v2"]
        assert data["plan_v2"]
        assert data["expanded_prompt_v2"]


def test_compile_fast_retries_worker_exception_then_succeeds(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir = compile_text_v2("Summarize this incident report.", offline_only=True)
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"
        mock_compiler.worker.process.side_effect = [Exception("temporary worker error"), mock_res]
        mock_compiler.cache = {}

        resp = client.post(
            "/compile/fast",
            json={"text": "hello", "mode": "default"},
            headers={"x-api-key": test_key},
        )

        assert resp.status_code == 200
        assert mock_compiler.worker.process.call_count == 2
        data = resp.json()
        assert data["system_prompt_v2"] == "sys"
        assert data["expanded_prompt_v2"] == "opt"


def test_compile_fast_retries_empty_worker_result_then_succeeds(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_res = MagicMock()
        mock_res.ir = compile_text_v2("Summarize this incident report.", offline_only=True)
        mock_res.system_prompt = "sys"
        mock_res.user_prompt = "user"
        mock_res.plan = "plan"
        mock_res.optimized_content = "opt"
        mock_compiler.worker.process.side_effect = [None, mock_res]
        mock_compiler.cache = {}

        resp = client.post(
            "/compile/fast",
            json={"text": "hello", "mode": "default"},
            headers={"x-api-key": test_key},
        )

        assert resp.status_code == 200
        assert mock_compiler.worker.process.call_count == 2
        data = resp.json()
        assert data["system_prompt_v2"] == "sys"
        assert data["expanded_prompt_v2"] == "opt"


def test_compile_fast_falls_back_after_two_worker_failures(test_key):
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.worker.process.side_effect = [
            Exception("first worker error"),
            Exception("second worker error"),
        ]
        mock_compiler.cache = {}

        resp = client.post(
            "/compile/fast",
            json={"text": "hello", "mode": "default"},
            headers={"x-api-key": test_key},
        )

        assert resp.status_code == 200
        assert mock_compiler.worker.process.call_count == 2
        data = resp.json()
        assert data["ir_v2"]["policy"]["risk_level"] == "low"
        assert any(
            item["category"] == "system"
            and item["severity"] == "warning"
            and "second worker error" in item["message"]
            for item in data["ir_v2"]["diagnostics"]
        )


def test_rate_limit(test_key):
    # Depending on how the rate limiter is implemented (in-memory global),
    # we might need to reset it or just spam enough requests.
    from api.auth import RATE_LIMIT_STORE

    RATE_LIMIT_STORE.clear()

    from api.auth import HEAVY_RATE_LIMIT_MAX_REQUESTS

    # Send allowed requests
    for _ in range(HEAVY_RATE_LIMIT_MAX_REQUESTS):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.return_value = MagicMock(
                ir=MagicMock(model_dump=lambda: {}),
                system_prompt="",
                user_prompt="",
                plan="",
                optimized_content="",
            )
            resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
            assert resp.status_code == 200

    # Next request should fail
    with patch("api.main.hybrid_compiler") as mock:
        mock.cache = {}
        resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
        assert resp.status_code == 429


def test_verify_api_key_rate_limit_is_atomic(monkeypatch):
    class SlowDict(dict):
        def __init__(self):
            super().__init__()
            self._lock = threading.Lock()
            self.active_gets = 0
            self.max_active_gets = 0

        def get(self, key, default=None):
            with self._lock:
                self.active_gets += 1
                self.max_active_gets = max(self.max_active_gets, self.active_gets)
            try:
                threading.Event().wait(0.05)
            finally:
                with self._lock:
                    self.active_gets -= 1
            return super().get(key, default)

    rate_limit_store = SlowDict()

    db = SessionLocal()
    key = APIKey(key="sk_atomic_db", owner="pytest")
    db.add(key)
    try:
        db.commit()
    except Exception:
        db.rollback()

    monkeypatch.setattr("api.auth.RATE_LIMIT_STORE", rate_limit_store)
    monkeypatch.setattr("api.auth.RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr("api.auth.RATE_LIMIT_WINDOW", 60)
    monkeypatch.setattr(verify_api_key, "_cleanup_counter", 0, raising=False)

    def run_check():
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.client = None
        try:
            verify_api_key(mock_request, "sk_atomic_db")

            return "ok"
        except HTTPException as exc:
            return exc.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run_check(), range(2)))
    finally:
        db.delete(key)
        db.commit()
        db.close()

    assert sorted(results, key=str) == [429, "ok"]
    assert rate_limit_store.max_active_gets == 1


def test_matches_admin_api_key_uses_dummy_compare_on_length_mismatch(monkeypatch):
    compare_calls = []

    def fake_compare_digest(left, right):
        compare_calls.append((left, right))
        return left == right

    monkeypatch.setattr("api.auth.secrets.compare_digest", fake_compare_digest)

    from api.auth import _matches_admin_api_key

    assert _matches_admin_api_key("short", "much-longer-admin-key") is False
    assert compare_calls == [("much-longer-admin-key", "much-longer-admin-key")]


def test_matches_admin_api_key_compares_provided_key_when_lengths_match(monkeypatch):
    compare_calls = []

    def fake_compare_digest(left, right):
        compare_calls.append((left, right))
        return left == right

    monkeypatch.setattr("api.auth.secrets.compare_digest", fake_compare_digest)

    from api.auth import _matches_admin_api_key

    assert _matches_admin_api_key("admin-key", "admin-key") is True
    assert compare_calls == [("admin-key", "admin-key")]


def test_compile_no_key():
    resp = client.post("/compile", json={"text": "hello", "v2": False})
    assert resp.status_code == 200


def test_compile_invalid_key():
    resp = client.post(
        "/compile", json={"text": "hello", "v2": False}, headers={"x-api-key": "invalid"}
    )
    assert resp.status_code == 200


def test_validate_no_key():
    with patch("api.main.get_compiler") as mock_get_compiler:
        mock_report = MagicMock()
        mock_report.weaknesses = []
        mock_report.strengths = ["clear"]
        mock_report.suggestions = ["none"]
        mock_report.score = 95
        mock_report.category_scores = {}
        mock_report.summary = "Looks good"
        mock_get_compiler.return_value.worker.analyze_prompt.return_value = mock_report

        resp = client.post("/validate", json={"text": "hello"})

    assert resp.status_code == 200


def test_optimize_no_key():
    with patch("api.main.get_compiler") as mock_get_compiler:
        mock_get_compiler.return_value.worker.optimize_prompt.return_value = ("short prompt", None)

        resp = client.post("/optimize", json={"text": "a much longer prompt"})

    assert resp.status_code == 200


def test_rag_stats_no_key():
    resp = client.get("/rag/stats")
    assert resp.status_code == 200


def test_rag_stats_no_key_falls_back_when_default_db_path_is_unwritable(tmp_path, monkeypatch):
    primary_db = tmp_path / "blocked" / "rag.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.delenv("PROMPTC_RAG_DB_PATH", raising=False)
    monkeypatch.setattr(simple_index, "DEFAULT_DB_PATH", str(primary_db))
    monkeypatch.chdir(workspace)

    real_connect = sqlite3.connect

    def flaky_connect(path, *args, **kwargs):
        if str(Path(path)) == str(primary_db):
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(path, *args, **kwargs)

    with patch("app.rag.simple_index.sqlite3.connect", side_effect=flaky_connect):
        resp = client.get("/rag/stats")

    assert resp.status_code == 200
    assert resp.json()["docs"] == 0
    assert (workspace / ".promptc" / primary_db.name).exists()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/compile", {"text": "hello", "v2": False}),
        ("post", "/validate", {"text": "hello"}),
        ("post", "/optimize", {"text": "a much longer prompt"}),
        ("get", "/rag/stats", None),
        ("post", "/rag/search", {"query": "compiler", "limit": 3}),
        ("post", "/rag/query", {"query": "compiler", "k": 3, "method": "keyword"}),
        ("post", "/rag/pack", {"query": "compiler", "k": 3, "method": "keyword"}),
    ],
)
def test_optional_auth_routes_require_key_when_global_enforcement_enabled(
    method, path, payload, monkeypatch
):
    monkeypatch.setenv("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "true")

    kwargs = {"json": payload} if payload is not None else {}
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 403


def test_optional_auth_routes_accept_valid_key_when_global_enforcement_enabled(
    test_key, monkeypatch
):
    monkeypatch.setenv("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "true")
    headers = {"x-api-key": test_key}

    compile_response = client.post("/compile", json={"text": "hello", "v2": False}, headers=headers)
    assert compile_response.status_code == 200

    with patch("api.main.get_compiler") as mock_get_compiler:
        mock_report = MagicMock()
        mock_report.weaknesses = []
        mock_report.strengths = ["clear"]
        mock_report.suggestions = ["none"]
        mock_report.score = 95
        mock_report.category_scores = {}
        mock_report.summary = "Looks good"
        mock_get_compiler.return_value.worker.analyze_prompt.return_value = mock_report

        validate_response = client.post("/validate", json={"text": "hello"}, headers=headers)

    assert validate_response.status_code == 200

    with patch("api.main.get_compiler") as mock_get_compiler:
        mock_get_compiler.return_value.worker.optimize_prompt.return_value = ("short prompt", None)

        optimize_response = client.post(
            "/optimize",
            json={"text": "a much longer prompt"},
            headers=headers,
        )

    assert optimize_response.status_code == 200

    rag_stats_response = client.get("/rag/stats", headers=headers)
    assert rag_stats_response.status_code == 200

    rag_search_response = client.post(
        "/rag/search",
        json={"query": "compiler", "limit": 3},
        headers=headers,
    )
    assert rag_search_response.status_code == 200

    rag_query_response = client.post(
        "/rag/query",
        json={"query": "compiler", "k": 3, "method": "fts"},
        headers=headers,
    )
    assert rag_query_response.status_code == 200

    rag_pack_response = client.post(
        "/rag/pack",
        json={"query": "compiler", "k": 3, "method": "fts"},
        headers=headers,
    )
    assert rag_pack_response.status_code == 200


@pytest.mark.parametrize(
    ("path", "payload", "expected_key"),
    [
        (
            "/agent-generator/export",
            {
                "system_prompt": "# Role\nYou help with triage.\n\n## Steps\n1. Review the input.",
                "format": "claude-sdk",
                "output_type": "python",
            },
            "python_code",
        ),
        (
            "/skills-generator/export",
            {
                "skill_definition": "# Skill\nA helper that searches docs.",
                "format": "langchain-tool",
                "output_type": "python",
            },
            "json_config",
        ),
    ],
)
def test_export_routes_follow_global_auth_enforcement(
    path, payload, expected_key, test_key, monkeypatch
):
    monkeypatch.setenv("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "true")

    unauthorized_response = client.post(path, json=payload)
    assert unauthorized_response.status_code == 403

    authorized_response = client.post(path, json=payload, headers={"x-api-key": test_key})
    assert authorized_response.status_code == 200
    assert expected_key in authorized_response.json()


def test_optional_auth_routes_reject_invalid_and_oversized_keys_when_global_enforcement_enabled(
    monkeypatch,
):
    monkeypatch.setenv("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "true")

    invalid_response = client.get("/rag/stats", headers={"x-api-key": "invalid"})
    assert invalid_response.status_code == 403

    oversized_response = client.get("/rag/stats", headers={"x-api-key": "x" * 257})
    assert oversized_response.status_code == 400
