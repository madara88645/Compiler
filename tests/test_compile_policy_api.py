from fastapi.testclient import TestClient

import api.routes.compile as compile_routes
from api.main import app
from app.compiler import compile_text_v2


client = TestClient(app)
VERIFICATION_TEXT = (
    "Build a CSV export endpoint. It must not expose user emails and should never "
    "log request bodies. Exclude soft-deleted rows. Do not add new dependencies."
)


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
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
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
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
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


def test_compile_endpoint_rerenders_v2_prompts_instead_of_using_stale_worker_text(monkeypatch):
    class WorkerResult:
        def __init__(self, text: str):
            self.ir = compile_text_v2(text, offline_only=True)
            self.system_prompt = "STALE SYSTEM PROMPT"
            self.user_prompt = "STALE USER PROMPT"
            self.plan = "STALE PLAN"
            self.optimized_content = "STALE EXPANDED PROMPT"

    class StaleCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            return WorkerResult(text)

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: StaleCompiler())

    response = client.post(
        "/compile",
        json={"text": VERIFICATION_TEXT, "v2": True, "render_v2_prompts": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_prompt_v2"] != "STALE SYSTEM PROMPT"
    assert "Before you finish, verify each of these against your answer:" in payload["system_prompt_v2"]
    assert payload["user_prompt_v2"] != "STALE USER PROMPT"
    assert payload["plan_v2"] != "STALE PLAN"


def test_compile_export_rerenders_v2_prompts_before_building_markdown(monkeypatch):
    class WorkerResult:
        def __init__(self, text: str):
            self.ir = compile_text_v2(text, offline_only=True)
            self.system_prompt = "STALE SYSTEM PROMPT"
            self.user_prompt = "STALE USER PROMPT"
            self.plan = "STALE PLAN"
            self.optimized_content = "STALE EXPANDED PROMPT"

    class StaleCompiler:
        def compile(self, text, mode="conservative", enable_context_retrieval=False):
            return WorkerResult(text)

    monkeypatch.setattr(compile_routes, "_get_compiler", lambda: StaleCompiler())

    response = client.post(
        "/compile/export",
        json={"text": VERIFICATION_TEXT, "v2": True, "render_v2_prompts": True},
    )

    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "STALE SYSTEM PROMPT" not in markdown
    assert "Before you finish, verify each of these against your answer:" in markdown
