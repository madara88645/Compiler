"""Tests for LLM Judge functionality."""

from app.testing.judge import LLMJudge, JudgeResult, ComparativeJudge, ComparisonResult
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


def test_comparison_result_model():
    """Test ComparisonResult model."""
    result = ComparisonResult(winner="A", reason="A is better", score_diff=15.5)
    assert result.winner == "A"
    assert result.reason == "A is better"
    assert result.score_diff == 15.5


def test_comparative_judge_mock_compare_length():
    """Test mock comparison heuristics based on length."""
    judge = ComparativeJudge()

    # Output A is longer
    result = judge.compare(
        output_a="Long output A with more details", output_b="Short B", task="Task"
    )
    assert result.winner == "A"
    assert result.score_diff > 0

    # Output B is longer
    result = judge.compare(
        output_a="Short A", output_b="Long output B with more details", task="Task"
    )
    assert result.winner == "B"
    assert result.score_diff > 0


def test_comparative_judge_mock_compare_paragraphs():
    """Test mock comparison heuristics based on paragraph structure."""
    judge = ComparativeJudge()

    # Output A has more paragraphs
    result = judge.compare(output_a="Para 1\n\nPara 2\n\nPara 3", output_b="Para 1", task="Task")
    assert result.winner == "A"

    # Output B has more paragraphs
    result = judge.compare(output_a="Para 1", output_b="Para 1\n\nPara 2\n\nPara 3", task="Task")
    assert result.winner == "B"


def test_comparative_judge_mock_compare_keywords():
    """Test mock comparison heuristics based on task keywords overlap."""
    judge = ComparativeJudge()

    # Task keyword overlap
    task = "write a function to calculate sum"

    # A has more task keywords
    result = judge.compare(
        output_a="function to calculate sum", output_b="just some words", task=task
    )
    assert result.winner == "A"

    # B has more task keywords
    result = judge.compare(
        output_a="just some words", output_b="function to calculate sum", task=task
    )
    assert result.winner == "B"


def test_comparative_judge_parse_response_json():
    """Test parsing standard JSON response."""
    judge = ComparativeJudge()

    response = '{"winner": "B", "reason": "Better formatted", "score_diff": 25}'
    result = judge._parse_response(response)

    assert result.winner == "B"
    assert result.reason == "Better formatted"
    assert result.score_diff == 25.0


def test_comparative_judge_parse_response_markdown():
    """Test parsing JSON wrapped in markdown blocks."""
    judge = ComparativeJudge()

    response = '```json\n{"winner": "A", "reason": "Detailed", "score_diff": 10}\n```'
    result = judge._parse_response(response)

    assert result.winner == "A"
    assert result.reason == "Detailed"
    assert result.score_diff == 10.0


def test_comparative_judge_parse_response_fallback():
    """Test fallback parsing when invalid JSON is returned."""
    judge = ComparativeJudge()

    # Fallback inferred from text
    response_b = "I think Output B is better because..."
    result_b = judge._parse_response(response_b)

    assert result_b.winner == "B"
    assert "Could not parse JSON" in result_b.reason

    response_a = "Output A wins because..."
    result_a = judge._parse_response(response_a)

    assert result_a.winner == "A"
    assert "Could not parse JSON" in result_a.reason
