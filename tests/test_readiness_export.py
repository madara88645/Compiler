"""Threshold tests for Readiness Slice 2 — executable .md/.json export.

These tests are the DEFINITION OF DONE for the Slice 2 task. An autonomous
agent (Codex) should implement the feature until every test here passes,
WITHOUT weakening or deleting any assertion in this file. The full existing
suite must also stay green (no regressions).

Contract being locked in:
  * POST /compile          -> response gains `readiness_markdown` (str) built
                              from app.readiness.markdown.report_to_markdown.
  * POST /compile/export   -> {"markdown": str, "json": dict, "filename": str}
                              markdown is a self-contained document with the
                              System Prompt, User Prompt, Plan and Readiness
                              sections; json carries the structured result.
  * Agent pack manifests   -> include the readiness markdown section so the
                              exported pack surfaces the readiness verdict.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# A prompt that yields a non-trivial readiness verdict ("clarify" + an
# unverifiable_reference signal), so the readiness sections are never empty.
EXPORT_TEXT = "use the AcmeCloud SDK to deploy my model"

VALID_VERDICTS = {"ready", "clarify", "risky", "noise"}


def _compile(text: str = EXPORT_TEXT, **extra) -> dict:
    payload = {"text": text, "v2": False, "render_v2_prompts": True}
    payload.update(extra)
    resp = client.post("/compile", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _export(text: str = EXPORT_TEXT, **extra) -> dict:
    payload = {"text": text, "v2": False, "render_v2_prompts": True}
    payload.update(extra)
    resp = client.post("/compile/export", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- 1. readiness_markdown wired into the /compile response -----------------


def test_compile_response_includes_readiness_markdown():
    body = _compile()
    assert "readiness_markdown" in body, "compile response must expose readiness_markdown"
    md = body["readiness_markdown"]
    assert isinstance(md, str) and md.strip()
    # Built from report_to_markdown -> "## Readiness: <verdict> — <title>"
    assert "## Readiness:" in md
    # Anti-gaming: the structured verdict must actually appear in the markdown.
    assert body["readiness"]["verdict"] in md


# --- 2. /compile/export returns markdown + json + filename ------------------


def test_compile_export_returns_markdown_json_and_filename():
    body = _export()
    assert isinstance(body.get("markdown"), str) and body["markdown"].strip()
    assert isinstance(body.get("json"), dict) and body["json"]
    assert isinstance(body.get("filename"), str) and body["filename"].endswith(".md")


# --- 3. export markdown contains all sections + real content ----------------


def test_compile_export_markdown_contains_all_sections():
    md = _export()["markdown"]
    assert "## System Prompt" in md
    assert "## User Prompt" in md
    assert "## Plan" in md
    assert "## Readiness:" in md


def test_compile_export_markdown_embeds_real_prompt_content():
    compiled = _compile()
    md = _export()["markdown"]
    # Export prefers v2 prompt fields (same as web tabs and CLI compile-export).
    sys_prompt = compiled.get("system_prompt_v2") or compiled["system_prompt"]
    assert sys_prompt[:30] in md


# --- 4. export json is structured and carries readiness + prompts ----------


def test_compile_export_json_has_readiness_and_prompts():
    data = _export()["json"]
    assert isinstance(data.get("readiness"), dict)
    assert data["readiness"].get("verdict") in VALID_VERDICTS
    for key in ("system_prompt", "user_prompt", "plan"):
        assert key in data, f"export json missing '{key}'"


# --- 5. agent pack manifests surface the readiness section ------------------


def _agent_pack_payload(pack_type: str = "project-pack") -> dict:
    return {
        "project_type": "web app",
        "stack": "FastAPI + Next.js",
        "goal": EXPORT_TEXT,
        "pack_type": pack_type,
    }


def test_agent_pack_includes_readiness_section():
    resp = client.post("/agent-packs/claude", json=_agent_pack_payload())
    assert resp.status_code == 200, resp.text
    manifest = resp.json()
    all_content = "\n".join(f["content"] for f in manifest["files"])
    assert "## Readiness:" in all_content, "agent pack must surface the readiness section"
