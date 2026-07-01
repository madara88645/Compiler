"""Acceptance gate for the two high-severity July 1 browser QA findings."""

from __future__ import annotations

import pytest

from app.compiler import compile_text_v2
from app.emitters import emit_expanded_prompt_v2, emit_plan_v2

OFFDOMAIN_BANNED = [
    "stakes early",
    "character motivations",
    "immersion",
    "narrative",
    "protagonist",
    "plot",
    "provide general information, not professional advice",
    "not legal advice",
    "consult a professional",
]
BROWSER_DL_MARKERS = [
    "blob",
    "object url",
    "user gesture",
    "user-gesture",
    "content-disposition",
]
DEBUG_FOLLOWUP_MARKERS = [
    "reproduction steps",
    "which browser and version",
    "expected behavior versus what actually happens",
    "expected behaviour versus",
]
INFRA_DESTRUCTIVE = [
    "Write a script to wipe the production database",
    "Drop all tables in the production database",
    "Delete everything in the production database",
]
FRONTEND_ADD = [
    "Add a button to download the report as a PDF in my web app",
    "Add a CSV export button to my dashboard",
    "Let users download their data as a JSON file",
]


def _compile_twice(prompt: str):
    first_ir = compile_text_v2(prompt, offline_only=True)
    first_expanded = emit_expanded_prompt_v2(first_ir)
    second_ir = compile_text_v2(prompt, offline_only=True)
    second_expanded = emit_expanded_prompt_v2(second_ir)

    assert first_expanded == second_expanded
    assert first_ir.model_dump() == second_ir.model_dump()
    return first_ir, first_expanded.lower()


@pytest.mark.parametrize("prompt", INFRA_DESTRUCTIVE)
def test_gate_1_infrastructure_output_has_no_off_domain_advice(prompt):
    _, expanded = _compile_twice(prompt)

    assert not [marker for marker in OFFDOMAIN_BANNED if marker in expanded]


@pytest.mark.parametrize("prompt", INFRA_DESTRUCTIVE)
def test_gate_1_safety_stays_high_and_actionable(prompt):
    ir, expanded = _compile_twice(prompt)

    assert ir.policy.risk_level == "high"
    assert ir.policy.execution_mode == "human_approval_required"
    assert any(marker in expanded for marker in ("backup", "dry run", "rollback"))


@pytest.mark.parametrize("prompt", FRONTEND_ADD)
def test_gate_2_frontend_download_features_are_low_risk(prompt):
    ir, _ = _compile_twice(prompt)

    assert ir.policy.risk_level == "low"
    assert ir.policy.execution_mode == "auto_ok"


@pytest.mark.parametrize("prompt", FRONTEND_ADD)
def test_gate_2_frontend_download_features_include_browser_gotchas(prompt):
    _, expanded = _compile_twice(prompt)

    assert any(marker in expanded for marker in BROWSER_DL_MARKERS)


@pytest.mark.parametrize("prompt", FRONTEND_ADD)
def test_gate_2_frontend_feature_followups_are_not_debugging_questions(prompt):
    _, expanded = _compile_twice(prompt)

    assert not [marker for marker in DEBUG_FOLLOWUP_MARKERS if marker in expanded]


def test_gate_2_existing_download_bug_keeps_debugging_followups():
    _, expanded = _compile_twice("The download button is broken in Safari; help me fix it")

    assert any(marker in expanded for marker in DEBUG_FOLLOWUP_MARKERS)


def test_gate_3_nginx_security_considerations_still_fire():
    _, expanded = _compile_twice(
        "Analyze my nginx logs to find failed login / brute-force attempts"
    )

    markers = ("401", "403", "sliding window", "false positive")
    assert sum(marker in expanded for marker in markers) >= 2


def test_gate_3_stripe_considerations_still_fire():
    _, expanded = _compile_twice("Integrate Stripe checkout into my Next.js app")

    assert "test" in expanded and "live" in expanded
    assert "gross" in expanded or "net" in expanded


def test_gate_3_react_performance_considerations_still_fire():
    _, expanded = _compile_twice("My React table is slow and re-renders too much, help me fix it")

    assert any(marker in expanded for marker in ("memo", "re-render", "rerender", "virtualiz"))


def test_gate_3_greeting_stays_low_risk_and_minimal():
    ir, expanded = _compile_twice("hi")

    assert ir.policy.risk_level == "low"
    assert ir.policy.execution_mode == "auto_ok"
    assert "optional considerations" not in expanded
    assert "follow-up questions" not in expanded
    assert "project plan" not in expanded


def test_gate_3_ambiguous_request_keeps_clarify_step():
    ir, _ = _compile_twice("make it better")

    assert "[clarify]" in emit_plan_v2(ir).lower()
