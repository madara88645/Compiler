"""Tests for Adversarial Testing Workflow."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.testing.adversarial import AdversarialGenerator
from app.optimizer.evolution import EvolutionEngine
from app.optimizer.models import OptimizationConfig, Candidate
from app.testing.models import TestSuite, TestCase
from app.llm.base import LLMProvider, LLMResponse


@pytest.fixture
def config():
    return OptimizationConfig(
        max_generations=2,
        adversarial_every=1,  # Trigger every generation for testing
    )


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=LLMProvider)
    # Mock adversarial generation response (list of dicts)
    provider.generate.return_value = LLMResponse(
        content='[{"description": "Adversarial Test", "input_variables": {"input": "attack"}, "assertions": [{"type": "not_contains", "value": "Fail", "error_message": "Failed"}]}]'
    )
    return provider


def test_adversarial_generator_mock(config):
    """Test AdversarialGenerator without LLM (mock mode)."""
    generator = AdversarialGenerator(provider=None)
    cases = generator.generate("Test Prompt")

    assert len(cases) > 0
    assert cases[0].description == "Prompt injection: Ignore instructions"


def test_adversarial_generator_with_llm(config, mock_provider):
    """Test AdversarialGenerator with LLM provider."""
    generator = AdversarialGenerator(provider=mock_provider)
    cases = generator.generate("Test Prompt")

    assert len(cases) == 1
    assert cases[0].description == "Adversarial Test"
    assert cases[0].input_variables["input"] == "attack"


@patch("app.optimizer.evolution.TestSuite")
def test_evolution_integration(mock_test_suite_cls, config):
    """
    Test EvolutionEngine integration.
    Verify that adversarial generation is triggered.
    """
    # Setup Mocks
    mock_judge = MagicMock()
    mock_judge.evaluate.return_value.score = 0.8
    # Make sure we don't crash on result access
    mock_judge.evaluate.return_value.passed_count = 1
    mock_judge.evaluate.return_value.failures = []

    # Mock adversarial result (different from main result to distinguish)
    mock_adv_res = MagicMock()
    mock_adv_res.score = 0.5
    mock_adv_res.passed_count = 0

    def evaluate_side_effect(cand, suite, base):
        if suite.name.startswith("Adversarial"):
            return mock_adv_res
        return mock_judge.evaluate.return_value

    mock_judge.evaluate.side_effect = evaluate_side_effect

    mock_mutator = MagicMock()
    # Mock mutation to return a candidate
    mock_mutator.generate_variations.return_value = [
        Candidate(generation=1, prompt_text="Mutated", mutation_type="test")
    ]
    # Attach provider to mutator so EvolutionEngine picks it up
    mock_mutator.provider = MagicMock()  # We don't need it to do real work here

    # Initialize Engine
    engine = EvolutionEngine(config, mock_judge, mock_mutator)

    # Inject a mock AdversarialGenerator to verify calls
    mock_adv_gen = MagicMock()
    mock_adv_gen.generate.return_value = [
        TestCase(id="adv1", description="MockAdv", input_variables={}, assertions=[])
    ]
    engine.adversarial = mock_adv_gen

    # Run
    suite = TestSuite(name="Test", prompt_file="p.txt", test_cases=[])
    engine.run("Initial", suite, Path("."))

    # Verification
    # 1. Check AdversarialGenerator called
    assert mock_adv_gen.generate.call_count >= 1

    # 2. Check TestSuite created with Adversarial name
    # The patched class was called. Check its args.
    ts_calls = mock_test_suite_cls.call_args_list
    assert any("Adversarial" in call.kwargs.get("name", "") for call in ts_calls)

    # 3. Check Judge evaluated the adversarial suite
    # The suite passed to judge is the return value of TestSuite(...)
    adv_suite_instance = mock_test_suite_cls.return_value

    judge_calls = mock_judge.evaluate.call_args_list
    # Look for a call where the second arg is our mock suite instance
    # Signature: evaluate(candidate, suite, base_dir)
    found = False
    for args, _ in judge_calls:
        if args[1] is adv_suite_instance:
            found = True
            break
    assert found, "Judge should have been called with the adversarial suite instance"
