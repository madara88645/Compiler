"""Tests for LLM Judge functionality."""

from app.testing.judge import LLMJudge, JudgeResult
from app.testing.models import Assertion
from app.testing.runner import TestRunner


def test_judge_result_model():
    """Test JudgeResult model."""
    result = JudgeResult(passed=True, reason="Test passed", score=0.95)
    assert result.passed is True
    assert result.reason == "Test passed"
    assert result.score == 0.95


def test_llm_judge_mock_contains():
    """Test mock evaluation for 'must contain' requirement."""
    judge = LLMJudge()  # No executor = mock mode

    result = judge.evaluate(requirement="Output must contain 'hello'", output="Hello world!")

    assert result.passed is True
    assert result.score == 1.0


def test_llm_judge_mock_contains_fail():
    """Test mock evaluation fails when content missing."""
    judge = LLMJudge()

    result = judge.evaluate(requirement="Output must contain 'goodbye'", output="Hello world!")

    assert result.passed is False
    assert result.score == 0.0


def test_llm_judge_mock_valid_json():
    """Test mock evaluation for valid JSON requirement."""
    judge = LLMJudge()

    result = judge.evaluate(requirement="Output must be valid JSON", output='{"key": "value"}')

    assert result.passed is True
    assert result.score == 1.0


def test_llm_judge_mock_invalid_json():
    """Test mock evaluation fails for invalid JSON."""
    judge = LLMJudge()

    result = judge.evaluate(requirement="Output must be valid JSON", output="not json at all")

    assert result.passed is False
    assert result.score == 0.0


def test_assertion_type_llm_judge():
    """Test that llm_judge is a valid assertion type."""
    assertion = Assertion(type="llm_judge", value="Must generate valid JSON", threshold=0.8)

    assert assertion.type == "llm_judge"
    assert assertion.threshold == 0.8


def test_runner_has_judge():
    """Test that TestRunner initializes with a judge."""
    runner = TestRunner()
    assert hasattr(runner, "judge")
    assert isinstance(runner.judge, LLMJudge)


def test_runner_check_assertion_llm_judge():
    """Test runner's _check_assertion handles llm_judge type."""
    runner = TestRunner()

    # Test valid JSON scenario - should pass
    assertion_pass = Assertion(type="llm_judge", value="Output must be valid JSON", threshold=0.5)
    result_pass = runner._check_assertion(assertion_pass, '{"key": "value"}')
    assert result_pass is True

    # Test invalid JSON scenario - should fail
    assertion_fail = Assertion(type="llm_judge", value="Output must be valid JSON", threshold=0.5)
    result_fail = runner._check_assertion(assertion_fail, "not json")
    assert result_fail is False
