"""Tests for CrossModelValidator."""

from unittest.mock import MagicMock
from app.optimizer.validator import CrossModelValidator, ValidationResult
from app.llm.base import LLMProvider, LLMResponse
from app.testing.models import TestCase, Assertion


class MockProvider(LLMProvider):
    def __init__(self, output_content: str):
        self.output_content = output_content

    def generate(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        return LLMResponse(content=self.output_content)


def test_validator_initialization():
    models = {"gpt-4": MockProvider("True"), "claude": MockProvider("True")}
    validator = CrossModelValidator(models)
    assert len(validator.validation_models) == 2


def test_validator_execution():
    # Setup mock providers
    # Assertion type 'contains' checks if output contains value

    # Model 1 passes
    p1 = MockProvider("Success output")
    # Model 2 fails
    p2 = MockProvider("Failure output")

    models = {"pass_model": p1, "fail_model": p2}
    validator = CrossModelValidator(models)

    # Test Case
    tc = TestCase(
        id="test1",
        description="Verify output contains Success",
        input_variables={},
        assertions=[Assertion(type="contains", value="Success")],
    )

    result = validator.validate("Test Prompt", [tc])

    # Check Result Structure
    assert isinstance(result, ValidationResult)
    assert len(result.scores) == 2

    # Check individual scores
    # pass_model should have score 1.0 (1/1 pass)
    assert result.scores["pass_model"] == 1.0
    # fail_model should have score 0.0 (0/1 pass)
    assert result.scores["fail_model"] == 0.0

    # Check details exist
    assert len(result.detailed_results) == 2

    pass_res = next(r for r in result.detailed_results if r.model_name == "pass_model")
    assert pass_res.passed

    fail_res = next(r for r in result.detailed_results if r.model_name == "fail_model")
    assert not fail_res.passed


def test_validator_error_handling():
    # Provider that raises exception
    err_provider = MagicMock(spec=LLMProvider)
    err_provider.generate.side_effect = Exception("API Error")

    models = {"broken_model": err_provider}
    validator = CrossModelValidator(models)

    tc = TestCase(id="t1", description="d", input_variables={}, assertions=[])

    result = validator.validate("P", [tc])

    # Ensure it didn't crash
    assert len(result.detailed_results) == 1
    res = result.detailed_results[0]
    assert res.error == "API Error"
    assert res.score == 0.0
    # Error models might be excluded from 'scores' dict?
    # Logic: "if not res.error: final_scores[name] = score"
    assert "broken_model" not in result.scores
