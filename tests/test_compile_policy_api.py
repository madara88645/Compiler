from fastapi.testclient import TestClient

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
    implied_persona = response.json()["ir_v2"]["metadata"]["implied_persona"]
    assert implied_persona["persona"] == "C# Developer"
    assert response.json()["ir_v2"]["role"] == "Expert C# Developer"
