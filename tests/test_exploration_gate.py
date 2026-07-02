"""Acceptance gate for exploration-mode scheduling.

The scheduler must add real scheduling on diagnostic/destructive work and must
stay completely silent — no tags, no pseudo-steps, no Working approach section —
on clear or trivial requests (anti-boilerplate / ADDS_VALUE rule).
"""

from __future__ import annotations

import pytest

from app.compiler import compile_text_v2
from app.emitters import emit_expanded_prompt_v2, emit_plan_v2

BOILERPLATE_BANNED = [
    "working approach",
    "çalışma yaklaşımı",
    "(explore)",
    "[decide]",
    "[verify]",
    "entropy",
]
OFFDOMAIN_BANNED = [
    "stakes early",
    "character motivations",
    "narrative",
    "protagonist",
    "not legal advice",
    "consult a professional",
]
TRIVIAL_OR_CLEAR = [
    "fix a typo in the README",
    "hi",
    "Summarize this article in 5 bullets",
    "Add a CSV export button to my dashboard",
]

DIAGNOSTIC = "The download button is broken in Safari; help me fix it"
MULTI_STEP_DIAGNOSTIC = "Find out why the build is broken and then fix it"
LOGIN_REGRESSION_ANCHOR = "Implement secure login sessions"
DESTRUCTIVE = "Write a script to wipe the production database"


def _compile_twice(prompt: str):
    """Compile twice and assert full determinism (dump, plan, expanded)."""
    first_ir = compile_text_v2(prompt, offline_only=True)
    first_plan = emit_plan_v2(first_ir)
    first_expanded = emit_expanded_prompt_v2(first_ir)
    second_ir = compile_text_v2(prompt, offline_only=True)

    assert first_plan == emit_plan_v2(second_ir)
    assert first_expanded == emit_expanded_prompt_v2(second_ir)
    assert first_ir.model_dump() == second_ir.model_dump()
    return first_ir, first_plan.lower(), first_expanded.lower()


@pytest.mark.parametrize("prompt", TRIVIAL_OR_CLEAR)
def test_gate_trivial_or_clear_requests_gain_no_scheduling_text(prompt):
    ir, plan, expanded = _compile_twice(prompt)

    assert all(step.scheduling is None for step in ir.steps)
    hits = [m for m in BOILERPLATE_BANNED if m in plan or m in expanded]
    assert not hits, f"scheduler leaked boilerplate on a clear request: {hits}"


def test_gate_pure_ambiguity_keeps_clarify_and_stays_unscheduled():
    ir, plan, expanded = _compile_twice("make it better")

    assert "[clarify]" in plan
    assert all(step.scheduling is None for step in ir.steps)
    assert not [m for m in BOILERPLATE_BANNED if m in plan or m in expanded]


def test_gate_login_prompt_regression_anchor_stays_silent():
    # Intents are polluted today ('logs?' matches inside 'login'); the
    # mandatory problem cue must keep the scheduler out of auth feature work.
    ir, plan, expanded = _compile_twice(LOGIN_REGRESSION_ANCHOR)

    assert all(step.scheduling is None for step in ir.steps)
    assert not [m for m in BOILERPLATE_BANNED if m in plan or m in expanded]


def test_gate_diagnostic_request_schedules_explore_and_working_approach():
    ir, plan, expanded = _compile_twice(DIAGNOSTIC)

    assert ir.steps and ir.steps[0].scheduling is not None
    assert ir.steps[0].scheduling.mode == "explore"
    assert "(explore)" in plan
    assert "working approach:" in expanded
    assert "- explore:" in expanded


def test_gate_multi_step_diagnostic_orders_explore_before_decide():
    ir, plan, _ = _compile_twice(MULTI_STEP_DIAGNOSTIC)

    assert "(explore)" in plan
    assert "[decide]" in plan
    assert plan.index("(explore)") < plan.index("[decide]")
    assert ir.metadata["uncertainty_profile"]["modes"]["decide"]["scheduled"] is True


def test_gate_destructive_request_keeps_policy_and_appends_verify():
    ir, plan, expanded = _compile_twice(DESTRUCTIVE)

    # Existing safety behavior must be untouched...
    assert ir.policy.risk_level == "high"
    assert ir.policy.execution_mode == "human_approval_required"
    assert "[policy]" in plan
    # ...with a verification step scheduled at the end of the plan.
    assert "[verify]" in plan
    assert plan.index("[policy]") < plan.index("[verify]")
    assert not [m for m in OFFDOMAIN_BANNED if m in expanded]


def test_gate_scheduling_survives_serialization_deterministically():
    ir, _, _ = _compile_twice(MULTI_STEP_DIAGNOSTIC)
    dump = ir.model_dump()

    scheduled = [s for s in dump["steps"] if s["scheduling"] is not None]
    assert scheduled, "expected scheduled steps in the serialized IR"
    for step in scheduled:
        assert step["scheduling"]["mode"] in ("explore", "decide", "execute", "verify")
        assert 0.0 <= step["scheduling"]["confidence"] <= 1.0
