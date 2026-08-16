from pathlib import Path

from app.optimizer.judge import JudgeAgent
from app.optimizer.models import Candidate
from app.testing.models import TestCase, TestResult, TestSuite


class FakeRunner:
    """Deterministic stand-in for TestRunner: returns pre-scripted TestResults keyed by case id,
    so JudgeAgent.evaluate's aggregation logic can be tested without compiling prompts or
    invoking an executor."""

    def __init__(self, results_by_case_id):
        self.results_by_case_id = results_by_case_id

    def run_case(self, case, template_text, defaults):
        return self.results_by_case_id[case.id]


def make_case(case_id):
    return TestCase(id=case_id, input_variables={}, assertions=[])


def make_candidate(prompt_text="Summarize the input text."):
    return Candidate(generation=0, prompt_text=prompt_text)


def make_suite(case_ids):
    return TestSuite(
        name="suite",
        prompt_file="unused.txt",
        test_cases=[make_case(cid) for cid in case_ids],
    )


def test_evaluate_zero_cases_returns_zero_score():
    judge = JudgeAgent(runner=FakeRunner({}))
    suite = make_suite([])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.avg_latency_ms == 0


def test_evaluate_all_pass_gives_score_one():
    results = {
        "a": TestResult(test_case_id="a", passed=True, output="ok", duration_ms=10.0),
        "b": TestResult(test_case_id="b", passed=True, output="ok", duration_ms=20.0),
    }
    judge = JudgeAgent(runner=FakeRunner(results))
    suite = make_suite(["a", "b"])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 1.0
    assert result.passed_count == 2
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.avg_latency_ms == 15.0
    assert result.failures == []


def test_evaluate_all_fail_gives_score_zero_and_collects_failure_messages():
    results = {
        "a": TestResult(
            test_case_id="a",
            passed=False,
            output="bad",
            duration_ms=5.0,
            failures=["missing keyword"],
        ),
    }
    judge = JudgeAgent(runner=FakeRunner(results))
    suite = make_suite(["a"])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 1
    assert result.error_count == 0
    assert result.failures == ["[a] Failed: missing keyword"]


def test_evaluate_mixed_pass_fail_error_computes_pass_rate_and_counts():
    results = {
        "a": TestResult(test_case_id="a", passed=True, output="ok", duration_ms=10.0),
        "b": TestResult(
            test_case_id="b", passed=False, output="bad", duration_ms=10.0, failures=["nope"]
        ),
        "c": TestResult(
            test_case_id="c", passed=False, output="", duration_ms=10.0, error="boom"
        ),
        "d": TestResult(test_case_id="d", passed=True, output="ok", duration_ms=10.0),
    }
    judge = JudgeAgent(runner=FakeRunner(results))
    suite = make_suite(["a", "b", "c", "d"])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 0.5
    assert result.passed_count == 2
    assert result.failed_count == 1
    assert result.error_count == 1
    assert result.avg_latency_ms == 10.0
    assert result.failures == ["[b] Failed: nope", "[c] Error: boom"]


def test_evaluate_defaults_to_mock_executor_backed_runner_when_no_runner_given():
    judge = JudgeAgent()

    assert judge.runner is not None
