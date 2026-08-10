"""tests/optimizer/test_judge.py — direct unit tests for app.optimizer.judge.JudgeAgent,
which had no dedicated test coverage. Uses the default MockExecutor-backed TestRunner
so no network/LLM calls are involved.
"""

from pathlib import Path

from app.optimizer.judge import JudgeAgent
from app.optimizer.models import Candidate
from app.testing.models import Assertion, TestCase, TestSuite


def _candidate(prompt_text: str = "Say hello politely.") -> Candidate:
    return Candidate(generation=0, prompt_text=prompt_text)


def _suite_with_cases(*cases: TestCase) -> TestSuite:
    return TestSuite(
        name="judge-suite",
        prompt_file="unused.txt",
        test_cases=list(cases),
    )


def test_evaluate_empty_suite_returns_zero_score():
    judge = JudgeAgent()
    suite = _suite_with_cases()

    result = judge.evaluate(_candidate(), suite, base_dir=Path("."))

    assert result.score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.avg_latency_ms == 0


def test_evaluate_all_cases_pass():
    # MockExecutor echoes "MOCKED RESPONSE. Prompt info: <prompt>", so an
    # assertion that the output contains a substring of the compiled prompt
    # (here, the literal instruction text) will pass deterministically.
    case = TestCase(
        id="case-1",
        assertions=[Assertion(type="contains", value="hello", target="output")],
    )
    suite = _suite_with_cases(case)
    judge = JudgeAgent()

    result = judge.evaluate(_candidate("Please say hello."), suite, base_dir=Path("."))

    assert result.score == 1.0
    assert result.passed_count == 1
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.failures == []


def test_evaluate_mixed_pass_and_fail_computes_partial_score():
    passing_case = TestCase(
        id="pass-case",
        assertions=[Assertion(type="contains", value="hello", target="output")],
    )
    failing_case = TestCase(
        id="fail-case",
        assertions=[
            Assertion(
                type="contains",
                value="this-substring-will-never-appear-xyz",
                target="output",
                error_message="expected marker missing",
            )
        ],
    )
    suite = _suite_with_cases(passing_case, failing_case)
    judge = JudgeAgent()

    result = judge.evaluate(_candidate("Please say hello."), suite, base_dir=Path("."))

    assert result.score == 0.5
    assert result.passed_count == 1
    assert result.failed_count == 1
    assert result.error_count == 0
    assert len(result.failures) == 1
    assert "expected marker missing" in result.failures[0]


def test_evaluate_all_cases_fail_scores_zero():
    case = TestCase(
        id="always-fails",
        assertions=[
            Assertion(type="contains", value="not-in-the-mock-response", target="output")
        ],
    )
    suite = _suite_with_cases(case)
    judge = JudgeAgent()

    result = judge.evaluate(_candidate(), suite, base_dir=Path("."))

    assert result.score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 1
    assert result.avg_latency_ms >= 0
