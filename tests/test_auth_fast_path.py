import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sqlite3
from pathlib import Path
from api.main import app
from api.auth import APIKey, SessionLocal
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


def test_rate_limit(test_key, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    from api.auth import RATE_LIMIT_STORE
    RATE_LIMIT_STORE.clear()

    # Send 10 requests (allowed)
    for _ in range(10):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.side_effect = Exception("Test Internal Error")
            # We mock the Request object to have a different IP address so it hits the rate limiter
            with patch("fastapi.Request.client") as mock_client:
                mock_client.host = "1.2.3.4"
                resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
                assert resp.status_code == 200

    # 11th request should fail with 429
    with patch("api.main.hybrid_compiler") as mock:
        mock.cache = {}
        with patch("fastapi.Request.client") as mock_client:
            mock_client.host = "1.2.3.4"
            resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
            assert resp.status_code == 429

def test_compile_no_key():
    resp = client.post("/compile", json={"text": "hello", "v2": False})
    assert resp.status_code == 200


def test_compile_invalid_key():
    resp = client.post(
        "/compile", json={"text": "hello", "v2": False}, headers={"x-api-key": "invalid"}
    )
    assert resp.status_code == 403


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
