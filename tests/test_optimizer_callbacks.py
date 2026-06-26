from unittest.mock import patch
from app.optimizer.callbacks import InteractiveCallback
from app.optimizer.models import Candidate, EvaluationResult


def test_interactive_callback_should_pause():
    # interactive_every = 0 (disabled)
    cb = InteractiveCallback(interactive_every=0)
    assert cb.should_pause(0) is False
    assert cb.should_pause(1) is False
    assert cb.should_pause(2) is False

    # interactive_every = 2
    cb2 = InteractiveCallback(interactive_every=2)
    assert cb2.should_pause(0) is False
    assert cb2.should_pause(1) is False
    assert cb2.should_pause(2) is True
    assert cb2.should_pause(3) is False
    assert cb2.should_pause(4) is True


def test_interactive_callback_methods():
    # Empty methods should execute without side-effects
    cb = InteractiveCallback(interactive_every=2)
    cb.on_start("initial", 1.0)
    cb.on_generation_start(1)
    assert cb._generation_count == 1

    cand = Candidate(prompt_text="hello", generation=0)
    res = EvaluationResult(
        score=0.5, passed_count=5, failed_count=5, error_count=0, avg_latency_ms=100.0
    )
    cb.on_candidate_evaluated(cand, res)
    cb.on_new_best(cand, 0.9)
    cb.on_complete(cand)


@patch("rich.prompt.Prompt.ask")
def test_human_intervention_choice_1(mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    # Choice 1: Continue (no change)
    mock_ask.return_value = "1"
    res = cb.on_human_intervention_needed(cand, 1)
    assert res is None


@patch("rich.prompt.Prompt.ask")
def test_human_intervention_choice_2(mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    # Choice 2 with empty feedback
    mock_ask.side_effect = ["2", ""]
    res = cb.on_human_intervention_needed(cand, 1)
    assert res is None

    # Choice 2 with actual feedback
    mock_ask.side_effect = ["2", "make it more professional"]
    res2 = cb.on_human_intervention_needed(cand, 1)
    assert res2 == {"type": "feedback", "content": "make it more professional"}


@patch("rich.prompt.Prompt.ask")
@patch("builtins.input")
def test_human_intervention_choice_3_cancel(mock_input, mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    # Choice 3: Manual edit -> Cancel
    mock_ask.return_value = "3"
    mock_input.side_effect = ["CANCEL"]
    res = cb.on_human_intervention_needed(cand, 1)
    assert res is None


@patch("rich.prompt.Prompt.ask")
@patch("builtins.input")
@patch("app.optimizer.utils.validate_human_input")
def test_human_intervention_choice_3_success(mock_validate, mock_input, mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    mock_ask.return_value = "3"
    mock_input.side_effect = ["modified prompt line 1", "modified prompt line 2", "END"]
    mock_validate.return_value = True

    res = cb.on_human_intervention_needed(cand, 1)
    assert res == {"type": "edit", "content": "modified prompt line 1\nmodified prompt line 2"}
    mock_validate.assert_called_once_with(
        "best prompt", "modified prompt line 1\nmodified prompt line 2"
    )


@patch("rich.prompt.Prompt.ask")
@patch("builtins.input")
@patch("app.optimizer.utils.validate_human_input")
def test_human_intervention_choice_3_validation_fail(mock_validate, mock_input, mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    mock_ask.return_value = "3"
    mock_input.side_effect = ["modified prompt", "END"]
    mock_validate.return_value = False

    res = cb.on_human_intervention_needed(cand, 1)
    assert res is None


@patch("rich.prompt.Prompt.ask")
@patch("builtins.input")
def test_human_intervention_choice_3_empty_input(mock_input, mock_ask):
    cb = InteractiveCallback(interactive_every=1)
    cand = Candidate(prompt_text="best prompt", generation=0)

    mock_ask.return_value = "3"
    mock_input.side_effect = ["END"]

    res = cb.on_human_intervention_needed(cand, 1)
    assert res is None
