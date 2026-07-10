"""Direct unit coverage for app.emitters._step_mode and _scheduled_modes.

These are the low-level primitives behind the "Working approach" section
suppression rule documented in test_emitters_scheduling.py — that section
must render only when explore/decide/verify was actually scheduled. The
existing tests exercise that rule end-to-end through emit_expanded_prompt_v2;
these tests pin the two small pure helpers directly, including edge cases
the integration tests don't reach (steps without a scheduling attribute,
an IR with no steps at all, and profile-only scheduling).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.emitters import _scheduled_modes, _step_mode
from app.models_v2 import IRv2, StepScheduling, StepV2


def _profile(explore: bool = False, decide: bool = False, verify: bool = False) -> dict:
    return {
        "modes": {
            "explore": {"scheduled": explore},
            "decide": {"scheduled": decide},
            "verify": {"scheduled": verify},
        }
    }


class TestStepMode:
    def test_returns_mode_when_scheduling_present(self) -> None:
        step = StepV2(type="task", text="x", scheduling=StepScheduling(mode="explore"))
        assert _step_mode(step) == "explore"

    def test_returns_none_when_scheduling_attribute_missing(self) -> None:
        step = SimpleNamespace(type="task", text="x")
        assert _step_mode(step) is None

    def test_returns_none_when_scheduling_is_none(self) -> None:
        step = StepV2(type="task", text="x", scheduling=None)
        assert _step_mode(step) is None

    def test_returns_none_when_mode_attribute_missing_on_scheduling(self) -> None:
        step = SimpleNamespace(scheduling=SimpleNamespace())
        assert _step_mode(step) is None


class TestScheduledModes:
    def test_no_steps_no_profile_returns_empty(self) -> None:
        ir = IRv2(steps=[], metadata={})
        assert _scheduled_modes(ir) == []

    def test_execute_only_step_is_not_surfaced(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="x", scheduling=StepScheduling(mode="execute"))],
            metadata={},
        )
        assert _scheduled_modes(ir) == []

    def test_explore_step_is_surfaced(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="x", scheduling=StepScheduling(mode="explore"))],
            metadata={},
        )
        assert _scheduled_modes(ir) == ["explore"]

    def test_profile_only_verify_is_surfaced_without_any_step(self) -> None:
        ir = IRv2(steps=[], metadata={"uncertainty_profile": _profile(verify=True)})
        assert _scheduled_modes(ir) == ["verify"]

    def test_missing_steps_attribute_is_tolerated(self) -> None:
        ir = SimpleNamespace(metadata={})
        assert _scheduled_modes(ir) == []

    def test_combines_step_modes_and_profile_modes_without_duplicates(self) -> None:
        ir = IRv2(
            steps=[StepV2(type="task", text="x", scheduling=StepScheduling(mode="explore"))],
            metadata={"uncertainty_profile": _profile(explore=True, decide=True)},
        )
        assert set(_scheduled_modes(ir)) == {"explore", "decide"}
