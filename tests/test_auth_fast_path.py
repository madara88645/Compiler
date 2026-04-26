from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sqlite3
from pathlib import Path
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

    # Send 10 requests (allowed)
    for _ in range(10):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.return_value = MagicMock(
                ir=MagicMock(model_dump=lambda: {}),
                system_prompt="",
                user_prompt="",
                plan="",
                optimized_content="",
            )
            client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})

    # 11th request should fail
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
        try:
            verify_api_key("sk_atomic_db")
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
