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
