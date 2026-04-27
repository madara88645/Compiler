from pathlib import Path

from app.compiler import compile_text, compile_text_v2
from app.emitters import emit_expanded_prompt, emit_expanded_prompt_v2, emit_plan_v2


def test_expanded_prompt_contains_input_and_example():
    txt = "arkadaşıma hediye öner futbol sever"
    ir = compile_text(txt)
    ep = emit_expanded_prompt(ir)
    assert "Genişletilmiş İstem" in ep or "Expanded Prompt" in ep
    assert "Input" in ep or "Girdi" in ep
    assert ("Örnek çıktı formatı" in ep) or ("Example output format" in ep)


def test_expanded_prompt_v2_surfaces_clarification_questions_without_diagnostics(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
    ir2 = compile_text_v2("Optimize this API and make it better", offline_only=True)

    ep = emit_expanded_prompt_v2(ir2, diagnostics=False)

    assert "Clarification Questions:" in ep
    assert "Which metric or aspect should be optimized?" in ep
    assert "Better in what sense" in ep


def test_plan_v2_starts_with_policy_gate_for_high_risk_prompt():
    ir2 = compile_text_v2("Analyze my stock portfolio allocation.", offline_only=True)

    plan = emit_plan_v2(ir2)

    first_line = plan.splitlines()[0]
    assert "[policy]" in first_line
    assert "human approval" in first_line.lower()


def test_expanded_prompt_v2_includes_policy_summary_without_inventing_requirements(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
    ir2 = compile_text_v2("Optimize this legal contract review workflow", offline_only=True)

    ep = emit_expanded_prompt_v2(ir2, diagnostics=False)

    assert "Policy:" in ep
    assert "human_approval_required" in ep
    assert "forbidden_tools=" in ep
    assert "Missing details will be filled" not in ep


def test_prompt_templates_discourage_invented_project_details():
    prompts_dir = Path("app/llm_engine/prompts")
    query_expansion = (prompts_dir / "query_expansion.md").read_text(encoding="utf-8").lower()
    worker_v1 = (prompts_dir / "worker_v1.md").read_text(encoding="utf-8").lower()

    assert "do not invent filenames" in query_expansion
    assert "do not invent functions" in query_expansion
    assert "do not add requirements" in worker_v1
    assert "mark assumptions explicitly" in worker_v1
