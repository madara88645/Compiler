import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.optimizer.evolution import EvolutionEngine
from app.optimizer.models import OptimizationConfig, OptimizationRun, Candidate, EvaluationResult
from app.testing.models import TestSuite, TestCase


@pytest.fixture
def mock_optimizer_components():
    judge = MagicMock()
    mutator = MagicMock()
    mutator.provider = MagicMock()

    # Mock default judge evaluation results: preserve pre-populated candidate result if it exists
    def evaluate_side_effect(candidate, suite, base_dir):
        if getattr(candidate, "result", None) is not None:
            return candidate.result
        return EvaluationResult(
            score=0.6,
            passed_count=6,
            failed_count=4,
            error_count=0,
            avg_latency_ms=50.0,
            failures=["Failed task A"],
        )

    judge.evaluate.side_effect = evaluate_side_effect

    # Mock default mutator generation
    var_cand = Candidate(
        id="var1",
        generation=1,
        prompt_text="variation 1 prompt",
        mutation_type="persona",
        result=EvaluationResult(
            score=0.9, passed_count=9, failed_count=1, error_count=0, avg_latency_ms=60.0
        ),
    )
    mutator.generate_variations.return_value = [var_cand]

    yield judge, mutator


@patch("app.optimizer.evolution.AdversarialGenerator")
@patch("app.optimizer.evolution.get_provider")
def test_evolution_engine_run_basic(mock_get_provider, mock_adv_gen_cls, mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    config = OptimizationConfig(
        max_generations=1,
        candidates_per_generation=1,
        target_score=0.8,
        model="gpt-4o",
        validation_models=[],
    )

    engine = EvolutionEngine(config, judge, mutator)

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    callback = MagicMock()

    run = engine.run("baseline prompt", suite, Path("."), callback=callback)

    assert isinstance(run, OptimizationRun)
    assert len(run.generations) == 1
    assert run.best_candidate is not None
    assert run.best_candidate.score == 0.9  # variation 1 has score 0.9

    callback.on_start.assert_called_once()
    callback.on_generation_start.assert_called_once_with(1)
    callback.on_complete.assert_called_once()


@patch("app.optimizer.evolution.AdversarialGenerator")
def test_evolution_engine_resume_from(mock_adv_gen_cls, mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    config = OptimizationConfig(max_generations=2, candidates_per_generation=1, target_score=0.95)

    engine = EvolutionEngine(config, judge, mutator)
    engine.run_history_manager = MagicMock()

    # Setup saved run
    baseline = Candidate(
        id="c0",
        generation=0,
        prompt_text="baseline",
        result=EvaluationResult(
            score=0.5, passed_count=5, failed_count=5, error_count=0, avg_latency_ms=50.0
        ),
    )
    saved_run = OptimizationRun(
        id="saved-run-123", config=config, generations=[[baseline]], total_cost=0.005
    )

    engine.run_history_manager.load_run.return_value = saved_run

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    callback = MagicMock()

    run = engine.resume_from(
        "saved-run-123", suite, Path("."), callback=callback, extra_generations=1
    )

    assert run.config.max_generations == 3  # extended by 1
    assert len(run.generations) == 4  # gen 0 was loaded, loop runs gen 1, 2, 3
    assert engine.cost_tracker.total_cost > 0.005


@patch("app.optimizer.evolution.AdversarialGenerator")
def test_evolution_engine_interactive_feedback(mock_adv_gen_cls, mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    # 1. Config with interactive_every = 1
    config = OptimizationConfig(
        max_generations=1, candidates_per_generation=1, interactive_every=1, target_score=1.0
    )

    # Mock mutator director feedback response
    feedback_cand = Candidate(
        id="fb1",
        generation=1,
        prompt_text="director feedback prompt",
        mutation_type="director_mode",
        result=EvaluationResult(
            score=0.95, passed_count=9, failed_count=1, error_count=0, avg_latency_ms=50.0
        ),
    )
    mutator.apply_director_feedback.return_value = [feedback_cand]

    engine = EvolutionEngine(config, judge, mutator)

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    # Mock callback to return director feedback command
    callback = MagicMock()
    callback.on_human_intervention_needed.return_value = {
        "type": "feedback",
        "content": "make it more direct",
    }

    run = engine.run("baseline", suite, Path("."), callback=callback)

    mutator.apply_director_feedback.assert_called_once()
    assert run.best_candidate.score == 0.95


@patch("app.optimizer.evolution.AdversarialGenerator")
def test_evolution_engine_interactive_manual_edit(mock_adv_gen_cls, mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    config = OptimizationConfig(
        max_generations=1, candidates_per_generation=1, interactive_every=1, target_score=1.0
    )

    engine = EvolutionEngine(config, judge, mutator)

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    # Mock callback to return manual edit command
    callback = MagicMock()
    callback.on_human_intervention_needed.return_value = {
        "type": "edit",
        "content": "manually edited prompt text",
    }

    # Setup judge to score the manual edit candidate high
    def evaluate_side_effect(cand, suite, base_dir):
        if cand.mutation_type == "human_edit":
            return EvaluationResult(
                score=0.99, passed_count=99, failed_count=1, error_count=0, avg_latency_ms=50.0
            )
        return EvaluationResult(
            score=0.5, passed_count=5, failed_count=5, error_count=0, avg_latency_ms=50.0
        )

    judge.evaluate.side_effect = evaluate_side_effect

    run = engine.run("baseline", suite, Path("."), callback=callback)
    assert run.best_candidate.score == 0.99
    assert run.best_candidate.mutation_type == "human_edit"


@patch("app.optimizer.evolution.AdversarialGenerator")
def test_evolution_engine_adversarial_loops(mock_adv_gen_cls, mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    config = OptimizationConfig(
        max_generations=1, candidates_per_generation=1, adversarial_every=1, target_score=1.0
    )

    # Mock adversarial generator to return cases
    adv_gen = MagicMock()
    mock_adv_gen_cls.return_value = adv_gen
    adv_gen.generate.return_value = [TestCase(id="adv1", input_variables={"in": "hack"})]

    # Mock mutator fix_vulnerabilities
    security_patch = Candidate(
        id="sec1",
        generation=1,
        prompt_text="secured prompt",
        mutation_type="security_patch",
        result=EvaluationResult(
            score=0.98, passed_count=98, failed_count=2, error_count=0, avg_latency_ms=50.0
        ),
    )
    mutator.fix_vulnerabilities.return_value = [security_patch]

    # Setup judge
    # Baseline: score=0.6, variation: score=0.9, adversarial check: score=0.4 (unsecured), security patch: score=0.98
    call_count = 0

    def evaluate_side_effect(cand, suite, base_dir):
        nonlocal call_count
        if "Adversarial" in suite.name:
            # First check returns fail/unsecured
            return EvaluationResult(
                score=0.4, passed_count=0, failed_count=1, error_count=0, avg_latency_ms=50.0
            )
        if cand.mutation_type == "security_patch":
            return EvaluationResult(
                score=0.98, passed_count=98, failed_count=2, error_count=0, avg_latency_ms=50.0
            )
        if cand.mutation_type == "baseline":
            return EvaluationResult(
                score=0.6, passed_count=6, failed_count=4, error_count=0, avg_latency_ms=50.0
            )
        return EvaluationResult(
            score=0.9, passed_count=9, failed_count=1, error_count=0, avg_latency_ms=50.0
        )

    judge.evaluate.side_effect = evaluate_side_effect

    engine = EvolutionEngine(config, judge, mutator)

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    run = engine.run("baseline", suite, Path("."))

    adv_gen.generate.assert_called_once()
    mutator.fix_vulnerabilities.assert_called_once()
    assert run.best_candidate.score == 0.98
    assert run.best_candidate.mutation_type == "security_patch"


@patch("app.optimizer.evolution.CrossModelValidator")
@patch("app.optimizer.evolution.get_provider")
def test_evolution_engine_validation_models(
    mock_get_provider, mock_validator_cls, mock_optimizer_components
):
    judge, mutator = mock_optimizer_components

    # Validation model configurations
    config = OptimizationConfig(
        max_generations=1,
        candidates_per_generation=1,
        target_score=0.8,
        validation_models=["openai:gpt-4o", "gpt-3.5-turbo", "claude-3", "other-model"],
    )

    # Mock provider calls
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    # Mock validator instance
    mock_val_instance = MagicMock()
    mock_validator_cls.return_value = mock_val_instance
    mock_val_instance.validate.return_value = MagicMock(scores={"openai:gpt-4o": 0.95})

    engine = EvolutionEngine(config, judge, mutator)

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    run = engine.run("baseline prompt", suite, Path("."))
    assert run is not None
    assert engine.validator is not None
    mock_validator_cls.assert_called_once()


def test_evolution_engine_validation_models_provider_failure(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    config = OptimizationConfig(max_generations=1, validation_models=["invalid:model"])
    # This should handle the provider loading failure gracefully without throwing
    with patch("app.optimizer.evolution.get_provider", side_effect=Exception("Load error")):
        engine = EvolutionEngine(config, judge, mutator)
        assert engine.validator is None


def test_evolution_engine_resume_from_errors(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    config = OptimizationConfig(max_generations=1)
    engine = EvolutionEngine(config, judge, mutator)
    engine.run_history_manager = MagicMock()

    # Case A: Run not found
    engine.run_history_manager.load_run.return_value = None
    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )
    with pytest.raises(ValueError, match="Run .* not found"):
        engine.resume_from("missing-run", suite, Path("."))

    # Case B: Corrupt run (no candidates)
    saved_run = OptimizationRun(id="corrupt-run", config=config, generations=[])
    engine.run_history_manager.load_run.return_value = saved_run
    with pytest.raises(ValueError, match="Corrupt run history: No candidates found"):
        engine.resume_from("corrupt-run", suite, Path("."))


def test_evolution_engine_no_callback_and_save_error(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    config = OptimizationConfig(max_generations=1, candidates_per_generation=1, target_score=0.8)
    engine = EvolutionEngine(config, judge, mutator)
    engine.run_history_manager = MagicMock()
    engine.run_history_manager.save_run.side_effect = Exception("Save failed")

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )
    # This should run and complete successfully despite the save failure (since it's caught and logged)
    run = engine.run("baseline prompt", suite, Path("."))
    assert run.best_candidate is not None


def test_human_intervention_edge_cases(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    config = OptimizationConfig(
        max_generations=1, candidates_per_generation=1, interactive_every=1, target_score=1.0
    )
    engine = EvolutionEngine(config, judge, mutator)
    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    # Case 1: Callback has no human intervention method
    callback_no_method = MagicMock()
    del callback_no_method.on_human_intervention_needed
    res1 = engine._request_human_intervention(
        Candidate(id="c0", prompt_text="baseline", generation=0),
        1,
        suite,
        Path("."),
        callback_no_method,
    )
    assert res1 == []

    # Case 2: Callback returns None
    callback_none = MagicMock()
    callback_none.on_human_intervention_needed.return_value = None
    res2 = engine._request_human_intervention(
        Candidate(id="c0", prompt_text="baseline", generation=0), 1, suite, Path("."), callback_none
    )
    assert res2 == []

    # Case 3: Callback returns legacy string (direct edit)
    callback_str = MagicMock()
    callback_str.on_human_intervention_needed.return_value = "new legacy string prompt"
    res3 = engine._request_human_intervention(
        Candidate(id="c0", prompt_text="baseline", generation=0), 1, suite, Path("."), callback_str
    )
    assert len(res3) == 1
    assert res3[0].prompt_text == "new legacy string prompt"
    assert res3[0].mutation_type == "human_edit"


def test_evolution_engine_budget_and_target_reached(mock_optimizer_components):
    judge, mutator = mock_optimizer_components

    # Target score is 0.5, baseline has 0.6. Should stop immediately.
    config = OptimizationConfig(max_generations=5, target_score=0.5)
    engine = EvolutionEngine(config, judge, mutator)
    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )
    run = engine.run("baseline", suite, Path("."))
    assert len(run.generations) == 0  # no generations evolved since baseline met target

    # Budget limit is reached.
    config_budget = OptimizationConfig(max_generations=5, target_score=1.0, budget_limit=0.001)
    engine_budget = EvolutionEngine(config_budget, judge, mutator)
    # Artificially set total_cost to 0.002
    engine_budget.cost_tracker.total_cost = 0.002
    run_budget = engine_budget.run("baseline", suite, Path("."))
    assert len(run_budget.generations) == 0  # stops before gen 1


def test_evolution_engine_empty_candidates(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    mutator.generate_variations.return_value = []

    config = OptimizationConfig(max_generations=1, candidates_per_generation=1, target_score=1.0)
    engine = EvolutionEngine(config, judge, mutator)
    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )
    run = engine.run("baseline", suite, Path("."))
    assert len(run.generations) == 1
    assert run.generations[0] == []


def test_cross_validation_exception(mock_optimizer_components):
    judge, mutator = mock_optimizer_components
    config = OptimizationConfig(
        max_generations=1,
        candidates_per_generation=1,
        target_score=1.0,
        validation_models=["openai:gpt-4o"],
    )
    engine = EvolutionEngine(config, judge, mutator)
    engine.validator = MagicMock()
    engine.validator.validate.side_effect = Exception("Validation failed internally")

    suite = TestSuite(
        name="test_suite",
        prompt_file="prompt.txt",
        test_cases=[TestCase(id="tc1", input_variables={"in": "1"})],
    )

    # Verify that cross validation exception is caught and does not halt execution
    engine._run_cross_validation(Candidate(id="c1", prompt_text="cand", generation=1), suite)
