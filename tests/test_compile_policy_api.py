from fastapi.testclient import TestClient

import api.routes.compile as compile_routes
from api.main import app


client = TestClient(app)


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
