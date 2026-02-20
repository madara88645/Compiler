import re
import time
import json
from typing import Dict, Any, Optional
from pathlib import Path
from .models import TestSuite, TestCase, TestResult, SuiteResult, Assertion
from .judge import LLMJudge
from app.compiler import compile_text
from app.emitters import emit_expanded_prompt


from app.llm.base import LLMProvider


# Mock Executor Interface for now
class Executor:
    def execute(self, prompt: str, config: Dict[str, Any]) -> str:
        raise NotImplementedError


class MockExecutor(Executor):
    def execute(self, prompt: str, config: Dict[str, Any]) -> str:
        # Simple deterministic mock: returns the prompt itself so assertions can check for injected content.
        # This allows the Optimizer to "win" by injecting the required keywords into the prompt.
        return f"MOCKED RESPONSE. Prompt info: {prompt}"


class LLMExecutor(Executor):
    """Executor that uses a real LLM provider."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def execute(self, prompt: str, config: Dict[str, Any]) -> str:
        # Copy config to avoid side effects
        run_config = config.copy()
        system_prompt = run_config.pop("system_prompt", None)
        response = self.provider.generate(prompt, system_prompt=system_prompt, **run_config)
        return response.content


class TestRunner:
    def __init__(self, executor: Optional[Executor] = None):
        self.executor = executor or MockExecutor()
        # Only pass real executors to judge, not MockExecutor
        judge_executor = executor if executor is not None else None
        self.judge = LLMJudge(executor=judge_executor)

    def run_suite(self, suite: TestSuite, base_dir: Path) -> SuiteResult:
        """Run all cases in a suite."""
        results = []
        passed_count = 0
        failed_count = 0
        error_count = 0
        start_total = time.perf_counter()

        # Resolve prompt path
        prompt_path = base_dir / suite.prompt_file
        if not prompt_path.exists():
            # Try relative to base_dir
            prompt_path = Path(suite.prompt_file)
            if not prompt_path.exists():
                # Fail everything if prompt is missing
                return SuiteResult(
                    suite_name=suite.name,
                    passed=0,
                    failed=len(suite.test_cases),
                    errors=0,
                    total_duration_ms=0,
                    results=[
                        TestResult(
                            test_case_id=tc.id,
                            passed=False,
                            output="",
                            duration_ms=0,
                            error=f"Prompt file not found: {suite.prompt_file}",
                        )
                        for tc in suite.test_cases
                    ],
                )

        # Compile prompt once to ensure validity (though we re-compile with vars for each test)
        try:
            # We assume compile_text works on raw text
            template_text = prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            return SuiteResult(
                suite_name=suite.name,
                passed=0,
                failed=0,
                errors=len(suite.test_cases),
                total_duration_ms=0,
                results=[
                    TestResult(
                        test_case_id=tc.id,
                        passed=False,
                        output="",
                        duration_ms=0,
                        error=f"Read error: {e}",
                    )
                    for tc in suite.test_cases
                ],
            )

        for case in suite.test_cases:
            res = self.run_case(case, template_text, suite.defaults)
            results.append(res)
            if res.error:
                error_count += 1
            elif res.passed:
                passed_count += 1
            else:
                failed_count += 1

        total_time = (time.perf_counter() - start_total) * 1000.0
        return SuiteResult(
            suite_name=suite.name,
            passed=passed_count,
            failed=failed_count,
            errors=error_count,
            total_duration_ms=total_time,
            results=results,
        )

    def run_case(self, case: TestCase, template_text: str, defaults: Dict[str, Any]) -> TestResult:
        """Run a single test case."""
        start = time.perf_counter()

        # Merge defaults with case args
        args = {**defaults, **case.input_variables}

        try:
            # 1. Compile prompt with variables
            # Note: The current 'compile_text' doesn't support Jinja-like injection directly in valid compilation logic
            # usually, but 'emit_user_prompt' might if the IR supports it.
            # For this sprint, we'll do a simple f-string like sub if not supported,
            # BUT the project has a template system.
            # Let's assume we use the 'template_app' filling logic or similar.
            # For now, we will use a basic string replace for keys locally to simulate "filling"
            # if the compiler doesn't handle it.
            # Actually, `compile_text` takes raw text. `emit_expanded_prompt` creates the final string.
            # We need a way to INJECT variables into the prompt BEFORE compilation or DURING emission.
            # Looking at existing code, `emit_expanded_prompt` takes `ir`.
            # There is no variable injection in the core compiler yet (it's static analysis).
            # So we will treat the input variables as just metadata we pass to the executor,
            # OR we format the text before compiling. Let's format before compiling.

            filled_text = template_text
            for k, v in args.items():
                filled_text = filled_text.replace(
                    f"{{{{{k}}}}}", str(v)
                )  # basic handlebars {{key}} replacement

            # Re-compile to get final prompt to send to LLM
            ir = compile_text(filled_text)

            # Emit the prompt string that would go to the LLM
            final_prompt_str = emit_expanded_prompt(ir)

            # 2. Execute
            output = self.executor.execute(
                final_prompt_str, {"model": case.model, "temperature": case.temperature}
            )

            # 3. Assert
            failures = []
            for assertion in case.assertions:
                if not self._check_assertion(assertion, output):
                    failures.append(
                        assertion.error_message
                        or f"Assertion failed: {assertion.type} {assertion.value}"
                    )

            duration = (time.perf_counter() - start) * 1000.0
            return TestResult(
                test_case_id=case.id,
                passed=len(failures) == 0,
                output=output,
                duration_ms=duration,
                failures=failures,
            )

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000.0
            return TestResult(
                test_case_id=case.id, passed=False, output="", duration_ms=duration, error=str(e)
            )

    def _check_assertion(self, assertion: Assertion, output: str) -> bool:
        if assertion.type == "contains":
            return str(assertion.value) in output
        elif assertion.type == "not_contains":
            return str(assertion.value) not in output
        elif assertion.type == "regex":
            return bool(re.search(str(assertion.value), output))
        elif assertion.type == "max_length":
            return len(output) <= int(assertion.value)
        elif assertion.type == "min_length":
            return len(output) >= int(assertion.value)
        elif assertion.type == "json_schema":
            # Basic validation that it IS json
            try:
                json.loads(output)
                return True  # TODO: Validate against schema if value is a schema dict
            except Exception:
                return False
        elif assertion.type == "llm_judge":
            # Use LLM Judge to evaluate
            requirement = str(assertion.value)
            result = self.judge.evaluate(requirement, output)
            # Use threshold if provided, otherwise require score >= 0.5
            threshold = assertion.threshold if assertion.threshold is not None else 0.5
            return result.score >= threshold
        return False
