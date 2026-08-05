"""Coverage gap: CostTracker.add_usage raises ValueError for an unknown
direction (only "input" and "output" are accepted).
"""
import pytest

from app.optimizer.costs import CostTracker


def test_add_usage_unknown_direction_raises_value_error():
    tracker = CostTracker()

    with pytest.raises(ValueError, match="Unknown direction: sideways"):
        tracker.add_usage("gpt-4o", 100, "sideways")


def test_add_usage_unknown_direction_does_not_mutate_state():
    tracker = CostTracker()

    with pytest.raises(ValueError):
        tracker.add_usage("gpt-4o", 100, "bogus")

    assert tracker.total_input_tokens == 0
    assert tracker.total_output_tokens == 0
    assert tracker.total_cost == 0.0
