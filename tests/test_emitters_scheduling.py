"""Rendering of exploration-mode scheduling in emit_plan_v2 / emit_expanded_prompt_v2.

Hard rule under test: when the scheduler did not engage (all scheduling None,
no profile mode scheduled) the rendered output is byte-identical to a build
without the scheduler — no tags, no pseudo-steps, no "Working approach" section.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.emitters import emit_expanded_prompt_v2, emit_plan_v2
from app.models_v2 import IRv2, PolicyV2, StepScheduling, StepV2


def _profile(explore: bool = False, decide: bool = False, verify: bool = False) -> dict:
    verify_reason = "destructive_operation" if verify else None
    return {
        "level": "elevated" if (explore or verify) else "low",
        "score": 2 if explore else 0,
        "signals": [],
        "modes": {
            "explore": {
                "scheduled": explore,
                "reason": "diagnostic_request" if explore else None,
            },
            "decide": {
                "scheduled": decide,
                "reason": "convergence_after_exploration" if decide else None,
            },
            "verify": {"scheduled": verify, "reason": verify_reason},
        },
    }


def _sched(mode: str) -> StepScheduling:
    reasons = {
        "explore": "diagnostic_request",
        "execute": "scoped_execution",
    }
    return StepScheduling(mode=mode, reason=reasons.get(mode), confidence=0.29)


class TestPlanModeRendering:
    def test_explore_step_renders_mode_tag_and_rationale(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="Find the cause", scheduling=_sched("explore"))],
            metadata={"uncertainty_profile": _profile(explore=True)},
        )

        plan = emit_plan_v2(ir)

        assert "1. [task] (explore) Find the cause" in plan
        assert "cause is not yet established" in plan

    def test_execute_tagged_step_renders_identically_to_untagged(self) -> None:
        untagged = IRv2(steps=[StepV2(type="task", text="Do the thing")])
        tagged = IRv2(
            steps=[StepV2(type="task", text="Do the thing", scheduling=_sched("execute"))]
        )

        assert emit_plan_v2(tagged) == emit_plan_v2(untagged)

    def test_decide_pseudo_step_follows_the_explore_step(self) -> None:
        ir = IRv2(
            steps=[
                StepV2(type="task", text="Find the cause", scheduling=_sched("explore")),
                StepV2(type="task", text="Apply the fix", scheduling=_sched("execute")),
            ],
            metadata={"uncertainty_profile": _profile(explore=True, decide=True)},
        )

        plan = emit_plan_v2(ir)

        assert "1. [task] (explore) Find the cause" in plan
        assert (
            "2. [decide] Choose one likely cause or approach to pursue before making changes."
            in plan
        )
        assert "3. [task] Apply the fix" in plan

    def test_verify_pseudo_step_appends_after_policy_and_steps(self) -> None:
        ir = IRv2(
            policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"),
            steps=[StepV2(type="task", text="Wipe the database", scheduling=_sched("execute"))],
            metadata={"uncertainty_profile": _profile(verify=True)},
        )

        plan = emit_plan_v2(ir)

        assert plan.startswith("1. [policy]")
        assert "2. [task] Wipe the database" in plan
        assert (
            "3. [verify] Re-check the result against the original request before treating it as done."
            in plan
        )

    def test_steps_without_scheduling_attribute_are_tolerated(self) -> None:
        ir = SimpleNamespace(
            metadata={},
            policy=SimpleNamespace(execution_mode="advice_only", risk_level="low"),
            steps=[SimpleNamespace(type="task", text="Do the thing")],
            tasks=[],
        )

        plan = emit_plan_v2(ir)

        assert "1. [task] Do the thing" in plan


class TestWorkingApproachSection:
    _LONG_TEXT = "The download button is broken in Safari; help me fix it"

    def test_section_renders_scheduled_modes_only(self) -> None:
        ir = IRv2(
            steps=[
                StepV2(type="task", text="Find the cause", scheduling=_sched("explore")),
                StepV2(type="task", text="Apply the fix", scheduling=_sched("execute")),
            ],
            metadata={
                "original_text": self._LONG_TEXT,
                "uncertainty_profile": _profile(explore=True, decide=True),
            },
        )

        ep = emit_expanded_prompt_v2(ir, diagnostics=False)

        assert "Working approach:" in ep
        assert "- Explore:" in ep
        assert "- Decide:" in ep
        assert "- Execute:" in ep
        assert "- Verify:" not in ep

    def test_section_suppressed_when_scheduler_silent(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="Summarize the article")],
            metadata={
                "original_text": "Summarize this article in five clear bullets",
                "uncertainty_profile": _profile(),
            },
        )

        ep = emit_expanded_prompt_v2(ir, diagnostics=False)

        assert "Working approach" not in ep

    def test_section_absent_when_profile_missing_entirely(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="Summarize the article")],
            metadata={"original_text": "Summarize this article in five clear bullets"},
        )

        ep = emit_expanded_prompt_v2(ir, diagnostics=False)

        assert "Working approach" not in ep
