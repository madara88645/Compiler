from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _compile(text: str) -> dict:
    resp = client.post(
        "/compile",
        json={"text": text, "v2": False, "render_v2_prompts": True},
    )
    assert resp.status_code == 200
    return resp.json()


def test_response_includes_readiness_verdict():
    body = _compile("use the AcmeCloud SDK to deploy my model")
    assert body["readiness"]["verdict"] == "clarify"
    kinds = {s["kind"] for s in body["readiness"]["signals"]}
    assert "unverifiable_reference" in kinds


def test_turkish_input_keeps_turkish_v2_output():
    body = _compile("Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?")
    from app.heuristics import detect_language

    assert detect_language(body["system_prompt_v2"]) == "tr"
