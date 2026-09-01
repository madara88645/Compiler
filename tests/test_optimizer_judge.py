"""Unit tests for JudgeAgent.evaluate() scoring arithmetic.

evaluate() is pure/deterministic given a TestRunner: it tallies pass/fail/error
counts and latency from TestResult objects. Existing tests
(test_optimizer_evolution.py, test_validator.py) mock JudgeAgent entirely, so
the arithmetic itself has no direct coverage. These tests exercise it with a
stub runner (no network/LLM calls).
"""

from pathlib import Path

from app.optimizer.judge import JudgeAgent
from app.optimizer.models import Candidate
from app.testing.models import TestCase, TestResult, TestSuite


class StubRunner:
    """Returns pre-scripted TestResults keyed by test case id."""

    def __init__(self, results_by_case_id):
        self.results_by_case_id = results_by_case_id
        self.calls = []

    def run_case(self, case, template_text, defaults):
        self.calls.append((case.id, template_text, defaults))
        return self.results_by_case_id[case.id]


def make_suite(case_ids):
    return TestSuite(
        name="suite",
        prompt_file="unused.txt",
        defaults={"key": "default"},
        test_cases=[TestCase(id=cid) for cid in case_ids],
    )


def make_candidate(prompt_text="hello world"):
    return Candidate(id="c1", generation=0, prompt_text=prompt_text)


def test_empty_suite_returns_zeroed_result():
    runner = StubRunner({})
    judge = JudgeAgent(runner=runner)
    suite = make_suite([])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.avg_latency_ms == 0
    assert result.failures == []


def test_all_cases_pass_yields_perfect_score():
    runner = StubRunner(
        {
            "tc1": TestResult(test_case_id="tc1", passed=True, output="ok", duration_ms=10.0),
            "tc2": TestResult(test_case_id="tc2", passed=True, output="ok", duration_ms=20.0),
        }
    )
    judge = JudgeAgent(runner=runner)
    suite = make_suite(["tc1", "tc2"])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 1.0
    assert result.passed_count == 2
    assert result.failed_count == 0
    assert result.error_count == 0
    assert result.avg_latency_ms == 15.0
    assert result.failures == []


def test_mixed_pass_fail_error_counts_and_score():
    runner = StubRunner(
        {
            "tc1": TestResult(test_case_id="tc1", passed=True, output="ok", duration_ms=10.0),
            "tc2": TestResult(
                test_case_id="tc2",
                passed=False,
                output="bad",
                duration_ms=10.0,
                failures=["assertion X failed"],
            ),
            "tc3": TestResult(
                test_case_id="tc3",
                passed=False,
                output="",
                duration_ms=10.0,
                error="executor timeout",
            ),
            "tc4": TestResult(test_case_id="tc4", passed=True, output="ok", duration_ms=10.0),
        }
    )
    judge = JudgeAgent(runner=runner)
    suite = make_suite(["tc1", "tc2", "tc3", "tc4"])

    result = judge.evaluate(make_candidate(), suite, Path("."))

    assert result.score == 0.5  # 2 passes / 4 cases
    assert result.passed_count == 2
    assert result.error_count == 1
    # failed_count = total - passed - errors, i.e. assertion failures only
    assert result.failed_count == 1
    assert result.avg_latency_ms == 10.0
    assert len(result.failures) == 2
    assert any("Error: executor timeout" in f for f in result.failures)
    assert any("Failed: assertion X failed" in f for f in result.failures)


def test_evaluate_passes_candidate_prompt_text_and_suite_defaults_to_runner():
    runner = StubRunner(
        {"tc1": TestResult(test_case_id="tc1", passed=True, output="ok", duration_ms=5.0)}
    )
    judge = JudgeAgent(runner=runner)
    suite = make_suite(["tc1"])
    candidate = make_candidate(prompt_text="custom candidate prompt")

    judge.evaluate(candidate, suite, Path("."))

    assert runner.calls == [("tc1", "custom candidate prompt", suite.defaults)]
