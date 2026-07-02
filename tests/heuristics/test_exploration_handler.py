"""ExplorationHandler: adaptive exploration-mode scheduling (R1-R4).

The handler derives a per-step latitude budget from signals the compiler has
already measured (problem cues in the user's own words, diagnostic intents,
ambiguity, complexity, risk/policy). It must be deterministic and must stay
silent (all ``scheduling`` = None) for clear, trivial requests.
"""

from __future__ import annotations

import pytest

from app.compiler import compile_text_v2
from app.heuristics.handlers.exploration import ExplorationHandler
from app.ir_contract import IR_SCHEDULING_REASONS, IR_STEP_MODES
from app.models_v2 import IRv2, PolicyV2, StepV2


@pytest.fixture
def handler():
    return ExplorationHandler()


def _ir2(
    text: str = "",
    steps: int = 1,
    intents: list[str] | None = None,
    policy: PolicyV2 | None = None,
    policy_reasons: list[str] | None = None,
    ambiguous: list[str] | None = None,
    complexity: str = "low",
    code_request: bool = False,
) -> IRv2:
    """Build a minimal IRv2 the way the pipeline leaves it before the handler runs."""
    return IRv2(
        intents=list(intents or []),
        steps=[StepV2(type="task", text=f"step {i + 1}") for i in range(steps)],
        policy=policy or PolicyV2(),
        metadata={
            "original_text": text,
            "ambiguous_terms": list(ambiguous or []),
            "complexity": complexity,
            "code_request": code_request,
            "policy_reasons": list(policy_reasons or []),
        },
    )


def _profile(ir: IRv2) -> dict:
    return ir.metadata["uncertainty_profile"]


# --------------------------------------------------------------------------
# R1 — explore
# --------------------------------------------------------------------------


class TestR1Explore:
    def test_cue_plus_ask_schedules_explore_on_first_step(self, handler):
        ir = _ir2("The download button is broken in Safari; help me fix it", steps=1)
        handler.handle(ir, None)

        sched = ir.steps[0].scheduling
        assert sched is not None
        assert sched.mode == "explore"
        assert sched.reason == "diagnostic_request"
        assert sched.confidence is not None and 0.0 <= sched.confidence <= 1.0

    def test_cue_plus_debug_intent_without_ask_schedules_explore(self, handler):
        ir = _ir2("My app crashes on startup with a stack trace", intents=["debug"])
        handler.handle(ir, None)

        assert ir.steps[0].scheduling is not None
        assert ir.steps[0].scheduling.mode == "explore"

    def test_polluted_intents_without_problem_cue_do_not_trigger(self, handler):
        # "Implement secure login sessions" gains troubleshooting/debug intents
        # today via the 'logs?' keyword bug; the mandatory problem cue must
        # keep explore off. Regression anchor.
        ir = _ir2(
            "Implement secure login sessions",
            intents=["code", "ambiguous", "troubleshooting", "debug"],
        )
        handler.handle(ir, None)

        assert all(step.scheduling is None for step in ir.steps)

    def test_diagnostic_ask_without_problem_cue_does_not_trigger(self, handler):
        ir = _ir2("fix a typo in the README")
        handler.handle(ir, None)

        assert all(step.scheduling is None for step in ir.steps)

    def test_problem_cue_without_ask_or_intent_does_not_trigger(self, handler):
        ir = _ir2("The build is broken again")
        handler.handle(ir, None)

        assert all(step.scheduling is None for step in ir.steps)

    def test_cue_must_match_on_word_boundary(self, handler):
        # "debugging" contains "bug"; without a standalone cue no explore.
        ir = _ir2("Write a tutorial about debugging techniques, help me structure it")
        handler.handle(ir, None)

        assert all(step.scheduling is None for step in ir.steps)


# --------------------------------------------------------------------------
# R2 — decide (pseudo-step, recorded in the profile)
# --------------------------------------------------------------------------


class TestR2Decide:
    def test_multi_step_diagnostic_schedules_decide(self, handler):
        ir = _ir2("Find out why the build is broken and then fix it", steps=2)
        handler.handle(ir, None)

        decide = _profile(ir)["modes"]["decide"]
        assert decide["scheduled"] is True
        assert decide["reason"] == "convergence_after_exploration"

    def test_single_step_diagnostic_does_not_schedule_decide(self, handler):
        ir = _ir2("The download button is broken in Safari; help me fix it", steps=1)
        handler.handle(ir, None)

        assert _profile(ir)["modes"]["decide"]["scheduled"] is False

    def test_decide_never_fires_without_explore(self, handler):
        ir = _ir2("Summarize this article in five bullets", steps=3)
        handler.handle(ir, None)

        assert _profile(ir)["modes"]["decide"]["scheduled"] is False


# --------------------------------------------------------------------------
# R3 — verify
# --------------------------------------------------------------------------


class TestR3Verify:
    def test_destructive_operation_schedules_verify(self, handler):
        ir = _ir2(
            "Write a script to wipe the production database",
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            policy_reasons=["destructive_operation"],
            code_request=True,
        )
        handler.handle(ir, None)

        verify = _profile(ir)["modes"]["verify"]
        assert verify["scheduled"] is True
        assert verify["reason"] == "destructive_operation"

    def test_high_risk_concrete_change_schedules_verify(self, handler):
        ir = _ir2(
            "Rotate the auth tokens for every tenant",
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            policy_reasons=["high_risk_domain:security"],
            code_request=True,
        )
        handler.handle(ir, None)

        verify = _profile(ir)["modes"]["verify"]
        assert verify["scheduled"] is True
        assert verify["reason"] == "high_risk_change"

    def test_high_risk_advice_only_prompt_stays_verify_free(self, handler):
        ir = _ir2(
            "Review this contract for risky clauses",
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            policy_reasons=["high_risk_domain:legal"],
            code_request=False,
        )
        handler.handle(ir, None)

        assert _profile(ir)["modes"]["verify"]["scheduled"] is False


# --------------------------------------------------------------------------
# R4 — execute backfill + silence guarantee
# --------------------------------------------------------------------------


class TestR4Backfill:
    def test_backfill_tags_remaining_steps_as_execute(self, handler):
        ir = _ir2("Find out why the build is broken and then fix it", steps=3)
        handler.handle(ir, None)

        assert ir.steps[0].scheduling.mode == "explore"
        for step in ir.steps[1:]:
            assert step.scheduling is not None
            assert step.scheduling.mode == "execute"
            assert step.scheduling.reason == "scoped_execution"

    def test_no_rule_fired_means_all_scheduling_none(self, handler):
        ir = _ir2("Summarize this article in five bullets", steps=3)
        handler.handle(ir, None)

        assert all(step.scheduling is None for step in ir.steps)

    def test_verify_alone_backfills_execute(self, handler):
        ir = _ir2(
            "Write a script to wipe the production database",
            steps=2,
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            policy_reasons=["destructive_operation"],
            code_request=True,
        )
        handler.handle(ir, None)

        for step in ir.steps:
            assert step.scheduling is not None
            assert step.scheduling.mode == "execute"


# --------------------------------------------------------------------------
# Uncertainty profile
# --------------------------------------------------------------------------


class TestUncertaintyProfile:
    def test_profile_always_written_even_when_silent(self, handler):
        ir = _ir2("Summarize this article in five bullets")
        handler.handle(ir, None)

        profile = _profile(ir)
        assert profile["level"] in ("low", "elevated", "high")
        assert isinstance(profile["score"], int)
        assert isinstance(profile["signals"], list)
        assert set(profile["modes"]) == {"explore", "decide", "verify"}

    def test_confidence_is_normalized_score(self, handler):
        ir = _ir2(
            "Find out why the build is broken and then fix it",
            steps=2,
            ambiguous=["better"],
            complexity="high",
        )
        handler.handle(ir, None)

        profile = _profile(ir)
        expected = round(profile["score"] / 7, 2)
        tagged = [s.scheduling for s in ir.steps if s.scheduling is not None]
        assert tagged, "expected scheduled steps"
        assert all(s.confidence == expected for s in tagged)

    def test_reasons_come_from_the_contract_enum(self, handler):
        ir = _ir2(
            "Find out why the build is broken and then fix it",
            steps=2,
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            policy_reasons=["destructive_operation"],
            code_request=True,
        )
        handler.handle(ir, None)

        for step in ir.steps:
            if step.scheduling is not None:
                assert step.scheduling.mode in IR_STEP_MODES
                assert step.scheduling.reason in IR_SCHEDULING_REASONS
        for entry in _profile(ir)["modes"].values():
            if entry["scheduled"]:
                assert entry["reason"] in IR_SCHEDULING_REASONS

    def test_handler_is_deterministic(self, handler):
        def run():
            ir = _ir2("Find out why the build is broken and then fix it", steps=2)
            handler.handle(ir, None)
            return ir.model_dump()

        assert run() == run()


# --------------------------------------------------------------------------
# End-to-end spot checks through the real pipeline
# --------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_diagnostic_prompt_gets_explore_first(self):
        ir = compile_text_v2(
            "The download button is broken in Safari; help me fix it",
            offline_only=True,
        )

        assert ir.steps, "expected steps"
        assert ir.steps[0].scheduling is not None
        assert ir.steps[0].scheduling.mode == "explore"

    def test_trivial_prompt_stays_unscheduled(self):
        ir = compile_text_v2("fix a typo in the README", offline_only=True)

        assert all(step.scheduling is None for step in ir.steps)
        assert ir.metadata["uncertainty_profile"]["modes"]["explore"]["scheduled"] is False

    def test_login_prompt_regression_anchor(self):
        ir = compile_text_v2("Implement secure login sessions", offline_only=True)

        assert all(step.scheduling is None for step in ir.steps)

    def test_destructive_prompt_keeps_policy_and_gains_verify(self):
        ir = compile_text_v2(
            "Write a script to wipe the production database", offline_only=True
        )

        assert ir.policy.risk_level == "high"
        assert ir.policy.execution_mode == "human_approval_required"
        assert ir.metadata["uncertainty_profile"]["modes"]["verify"]["scheduled"] is True

    def test_scheduling_round_trips_through_model_dump(self):
        ir = compile_text_v2(
            "Find out why the build is broken and then fix it", offline_only=True
        )
        restored = IRv2.model_validate(ir.model_dump())

        assert [s.scheduling for s in restored.steps] == [s.scheduling for s in ir.steps]

    def test_scheduling_preserves_unknown_future_fields(self):
        restored = IRv2.model_validate(
            {
                "steps": [
                    {
                        "type": "task",
                        "text": "step",
                        "scheduling": {"mode": "explore", "route_hint": "scout-pack"},
                    }
                ]
            }
        )

        dumped = restored.steps[0].scheduling.model_dump()
        assert dumped["mode"] == "explore"
        assert dumped["route_hint"] == "scout-pack"
