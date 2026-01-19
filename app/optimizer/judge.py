from __future__ import annotations
from pathlib import Path
from app.testing.models import TestSuite
from app.testing.runner import TestRunner
from app.llm.base import LLMProvider
from .models import Candidate, EvaluationResult


class JudgeAgent:
    """
    Agent 2: The Judge.
    Wraps the TestRunner to evaluate a candidate prompt.
    """

    def __init__(self, runner: TestRunner = None, provider: LLMProvider = None):
        if runner:
            self.runner = runner
        elif provider:
            from app.llm.adapter import ProviderExecutor
            executor = ProviderExecutor(provider)
            self.runner = TestRunner(executor=executor)
        else:
            self.runner = TestRunner()  # Uses default executor (Mock)

    def evaluate(self, candidate: Candidate, suite: TestSuite, base_dir: Path) -> EvaluationResult:
        """
        Runs the test suite using the candidate's prompt text.
        """

        # We need to temporarily inject the candidate's prompt into the suite execution.
        # The TestRunner usually reads from a file `suite.prompt_file`.
        # We will override this by using a specialized method or passing the text directly.
        # Looking at TestRunner.run_case, it takes `template_text`.
        # We can implement a helper in TestRunner or just bypass `run_suite`
        # and iterate cases manually here.

        # Let's iterate manually to inject the text.

        total_cases = len(suite.test_cases)
        if total_cases == 0:
            return EvaluationResult(
                score=0.0, passed_count=0, failed_count=0, error_count=0, avg_latency_ms=0
            )

        failures = []
        passes = 0
        errors = 0
        total_latency = 0.0

        for case in suite.test_cases:
            # We use the candidate.prompt_text instead of reading from file
            result = self.runner.run_case(case, candidate.prompt_text, suite.defaults)
            total_latency += result.duration_ms

            if result.passed:
                passes += 1
            elif result.error:
                errors += 1
                failures.append(f"[{case.id}] Error: {result.error}")
            else:
                # Failed assertion
                failures.append(f"[{case.id}] Failed: {', '.join(result.failures)}")

        # Calculate Score
        # Simple algorithm: Pass Rate
        score = passes / total_cases

        return EvaluationResult(
            score=score,
            passed_count=passes,
            failed_count=len(suite.test_cases) - passes - errors,
            error_count=errors,
            avg_latency_ms=total_latency / total_cases if total_cases else 0,
            failures=failures,
        )
