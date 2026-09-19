from fastapi.testclient import TestClient

import api.routes.compile as compile_routes
from api.main import app


client = TestClient(app)

CHECKLIST_TEXT = (
    "Build a CSV export endpoint. It must not expose user emails and should never "
    "log request bodies. Exclude soft-deleted rows. Do not add new dependencies."
)


def _patch_empty_ir_compiler(monkeypatch):
    class EmptyWorkerResult:
        ir = None
        system_prompt = ""
        user_prompt = ""
        plan = ""
        optimized_content = ""

    class EmptyCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            return EmptyWorkerResult()

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: EmptyCompiler())


def _patch_broken_compiler(monkeypatch):
    class BrokenCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            raise RuntimeError("worker exploded")

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: BrokenCompiler())


def _patch_stale_prompt_compiler(monkeypatch):
    class StaleWorkerResult:
        ir = None
        system_prompt = "STALE SYSTEM PROMPT"
        user_prompt = "STALE USER PROMPT"
        plan = "STALE PLAN"
        optimized_content = "STALE EXPANDED PROMPT"

    class StaleCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            return StaleWorkerResult()

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: StaleCompiler())


def _patch_valid_ir_stale_prompt_compiler(monkeypatch):
    class StaleWorkerResult:
        ir = compile_routes.compile_text_v2(CHECKLIST_TEXT, offline_only=True)
        system_prompt = "STALE SYSTEM PROMPT"
        user_prompt = "STALE USER PROMPT"
        plan = "STALE PLAN"
        optimized_content = "STALE EXPANDED PROMPT"

    class StaleCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            return StaleWorkerResult()

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: StaleCompiler())


def test_compile_endpoint_exposes_policy_in_ir_v2():
    response = client.post("/compile", json={"text": "Analyze my stock portfolio.", "v2": False})

    assert response.status_code == 200
    payload = response.json()
    assert "ir" in payload
    assert "ir_v2" in payload
    assert payload["ir_v2"]["policy"]["risk_level"] == "high"
    assert payload["ir_v2"]["policy"]["execution_mode"] == "human_approval_required"


def test_compile_endpoint_applies_implied_persona_in_local_v2_pipeline():
    response = client.post("/compile", json={"text": 'Console.WriteLine("hello");', "v2": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ir_v2"]["metadata"]["implied_persona"]["persona"] == "C# Developer"
    assert payload["ir_v2"]["role"] == "Expert C# Developer"


def test_compile_endpoint_falls_back_when_worker_ir_is_empty(monkeypatch):
    class EmptyWorkerResult:
        ir = None
        system_prompt = ""
        user_prompt = ""
        plan = ""
        optimized_content = ""

    class EmptyCompiler:
        def compile(self, text, mode="conservative"):
            return EmptyWorkerResult()

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: EmptyCompiler())

    response = client.post(
        "/compile",
        json={
            "text": "Analyze my stock portfolio.",
            "v2": True,
            "render_v2_prompts": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ir_v2"]["policy"]["risk_level"] == "high"
    assert payload["system_prompt_v2"]
    assert payload["expanded_prompt_v2"]


def test_compile_endpoint_falls_back_when_worker_ir_dict_is_empty(monkeypatch):
    class EmptyWorkerResult:
        ir = {}
        system_prompt = ""
        user_prompt = ""
        plan = ""
        optimized_content = ""

    class EmptyCompiler:
        def compile(self, text, mode="conservative"):
            return EmptyWorkerResult()

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: EmptyCompiler())

    response = client.post(
        "/compile",
        json={
            "text": "Analyze my stock portfolio.",
            "v2": True,
            "render_v2_prompts": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ir_v2"]["policy"]["risk_level"] == "high"
    assert payload["plan_v2"]
    assert payload["expanded_prompt_v2"]


def test_compile_endpoint_renders_checklist_when_worker_returns_empty_ir(monkeypatch):
    _patch_empty_ir_compiler(monkeypatch)

    response = client.post("/compile", json={"text": CHECKLIST_TEXT, "v2": True})

    assert response.status_code == 200
    payload = response.json()
    assert "Before you finish, verify each of these against your answer:" in (
        payload["system_prompt_v2"] or ""
    )
    assert "expose user emails" in (payload["system_prompt_v2"] or "")


def test_compile_export_keeps_checklist_when_worker_returns_empty_ir(monkeypatch):
    _patch_empty_ir_compiler(monkeypatch)

    response = client.post("/compile/export", json={"text": CHECKLIST_TEXT, "v2": True})

    assert response.status_code == 200
    payload = response.json()
    assert "Before you finish, verify each of these against your answer:" in payload["markdown"]
    assert "soft-deleted rows" in payload["markdown"]


def test_compile_export_keeps_checklist_when_worker_raises(monkeypatch):
    _patch_broken_compiler(monkeypatch)

    response = client.post("/compile/export", json={"text": CHECKLIST_TEXT, "v2": True})

    assert response.status_code == 200
    payload = response.json()
    assert "Before you finish, verify each of these against your answer:" in payload["markdown"]
    assert "add new dependencies" in payload["markdown"]


def test_compile_endpoint_ignores_stale_worker_prompts_when_falling_back(monkeypatch):
    _patch_stale_prompt_compiler(monkeypatch)

    response = client.post("/compile", json={"text": CHECKLIST_TEXT, "v2": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_prompt_v2"] != "STALE SYSTEM PROMPT"
    assert "Before you finish, verify each of these against your answer:" in (
        payload["system_prompt_v2"] or ""
    )


def test_compile_endpoint_rerenders_v2_prompts_from_ir_when_requested(monkeypatch):
    _patch_valid_ir_stale_prompt_compiler(monkeypatch)

    response = client.post(
        "/compile",
        json={"text": CHECKLIST_TEXT, "v2": True, "render_v2_prompts": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_prompt_v2"] != "STALE SYSTEM PROMPT"
    assert payload["user_prompt_v2"] != "STALE USER PROMPT"
    assert payload["plan_v2"] != "STALE PLAN"
    assert payload["expanded_prompt_v2"] != "STALE EXPANDED PROMPT"
    assert "Before you finish, verify each of these against your answer:" in (
        payload["system_prompt_v2"] or ""
    )
    assert "It must not expose user emails and should never log request bodies." in (
        payload["system_prompt_v2"] or ""
    )
    assert "Goals:" in (payload["user_prompt_v2"] or "")
    assert "Build a CSV export endpoint" in (payload["plan_v2"] or "")
    assert "Policy: risk=medium; execution=human_approval_required" in (
        payload["expanded_prompt_v2"] or ""
    )


def test_compile_export_rerenders_v2_prompts_from_ir_when_requested(monkeypatch):
    _patch_valid_ir_stale_prompt_compiler(monkeypatch)

    response = client.post(
        "/compile/export",
        json={"text": CHECKLIST_TEXT, "v2": True, "render_v2_prompts": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "STALE SYSTEM PROMPT" not in payload["markdown"]
    assert "STALE USER PROMPT" not in payload["markdown"]
    assert "STALE PLAN" not in payload["markdown"]
    assert "Before you finish, verify each of these against your answer:" in payload["markdown"]
    assert "soft-deleted rows" in payload["markdown"]
    assert payload["json"]["expanded_prompt_v2"] != "STALE EXPANDED PROMPT"
