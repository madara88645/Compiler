"""Tests for User Feedback Loop in Evolution Engine."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.optimizer.evolution import EvolutionEngine
from app.optimizer.models import OptimizationConfig, Candidate, EvaluationResult
from app.testing.models import TestSuite
from app.optimizer.callbacks import EvolutionCallback


@pytest.fixture
def mock_components():
    config = OptimizationConfig(max_generations=2, interactive_every=1)
    judge = MagicMock()
    judge.evaluate.return_value = EvaluationResult(
        score=0.5, passed_count=1, failed_count=1, error_count=0, avg_latency_ms=10
    )
    mutator = MagicMock()
    mutator.apply_director_feedback.return_value = [
        Candidate(generation=1, prompt_text="Feedback Applied", mutation_type="director_feedback")
    ]
    # Set provider to None to avoid property access issues if any
    mutator.provider = None

    return config, judge, mutator


def test_request_human_intervention_feedback(mock_components):
    """Verify handling of structured 'feedback' response."""
    config, judge, mutator = mock_components
    engine = EvolutionEngine(config, judge, mutator)

    current_best = Candidate(generation=0, prompt_text="Original", mutation_type="baseline")
    current_best.result = judge.evaluate.return_value  # Set result so it has score

    # Mock Callback
    callback = MagicMock(spec=EvolutionCallback)
    # Return structured feedback
    callback.on_human_intervention_needed.return_value = {
        "type": "feedback",
        "content": "Make it shorter",
    }

    candidates = engine._request_human_intervention(
        current_best, 1, MagicMock(spec=TestSuite), Path("."), callback
    )

    # Validation
    assert len(candidates) == 1
    assert candidates[0].prompt_text == "Feedback Applied"
    assert candidates[0].mutation_type == "director_feedback"

    # Check mutator called correctly
    mutator.apply_director_feedback.assert_called_once_with(current_best, "Make it shorter")


def test_request_human_intervention_edit(mock_components):
    """Verify handling of structured 'edit' response."""
    config, judge, mutator = mock_components
    engine = EvolutionEngine(config, judge, mutator)

    current_best = Candidate(generation=0, prompt_text="Original", mutation_type="baseline")
    current_best.result = judge.evaluate.return_value

    callback = MagicMock(spec=EvolutionCallback)
    # Return structure edit
    callback.on_human_intervention_needed.return_value = {"type": "edit", "content": "Manual Edit"}

    candidates = engine._request_human_intervention(
        current_best, 1, MagicMock(spec=TestSuite), Path("."), callback
    )

    assert len(candidates) == 1
    assert candidates[0].prompt_text == "Manual Edit"
    assert candidates[0].mutation_type == "human_edit"

    # Mutator NOT called for edit
    mutator.apply_director_feedback.assert_not_called()


def test_request_human_intervention_legacy_string(mock_components):
    """Verify handling of legacy string response."""
    config, judge, mutator = mock_components
    engine = EvolutionEngine(config, judge, mutator)

    current_best = Candidate(generation=0, prompt_text="Original", mutation_type="baseline")
    current_best.result = judge.evaluate.return_value

    callback = MagicMock(spec=EvolutionCallback)
    # Return legacy string
    callback.on_human_intervention_needed.return_value = "Legacy Edit"

    candidates = engine._request_human_intervention(
        current_best, 1, MagicMock(spec=TestSuite), Path("."), callback
    )

    assert len(candidates) == 1
    assert candidates[0].prompt_text == "Legacy Edit"

    mutator.apply_director_feedback.assert_not_called()
