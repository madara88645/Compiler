import orjson
import re
import time
import jsonschema
from typing import Dict, Any, Optional
from pathlib import Path
from .models import TestSuite, TestCase, TestResult, SuiteResult, Assertion
from .judge import LLMJudge
from app.compiler import compile_text, compile_text_v2
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
    __test__ = False

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
            ir_v2 = compile_text_v2(filled_text, offline_only=True)

            # Emit the prompt string that would go to the LLM
            final_prompt_str = emit_expanded_prompt(ir)

            # 2. Execute
            output = self.executor.execute(
                final_prompt_str, {"model": case.model, "temperature": case.temperature}
            )

            # 3. Assert
            failures = []
            for assertion in case.assertions:
                if not self._check_assertion(assertion, output, ir_v2):
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
            import logging

            logging.getLogger(__name__).error(f"Test runner error: {e}")
            duration = (time.perf_counter() - start) * 1000.0
            return TestResult(
                test_case_id=case.id,
                passed=False,
                output="",
                duration_ms=duration,
                error="An internal error occurred.",
            )

    def _check_assertion(self, assertion: Assertion, output: str, ir_v2=None) -> bool:
        policy = getattr(ir_v2, "policy", None)

        if assertion.target == "policy" and policy is not None:
            if assertion.type == "risk_at_least":
                ordering = {"low": 1, "medium": 2, "high": 3}
                expected = ordering.get(str(assertion.value), 0)
                actual = ordering.get(policy.risk_level, 0)
                return actual >= expected
            elif assertion.type == "execution_mode_is":
                return policy.execution_mode == str(assertion.value)
            elif assertion.type == "policy_contains":
                combined = " ".join(
                    policy.risk_domains
                    + policy.allowed_tools
                    + policy.forbidden_tools
                    + policy.sanitization_rules
                    + [policy.data_sensitivity, policy.execution_mode, policy.risk_level]
                )
                return str(assertion.value) in combined

        if assertion.target == "ir" and ir_v2 is not None:
            # Bolt Optimization: Use model_dump_json for fast Rust-powered serialization
            payload = ir_v2.model_dump_json()
            if assertion.type in {"contains", "includes"}:
                return str(assertion.value) in payload
            elif assertion.type == "not_contains":
                return str(assertion.value) not in payload
            elif assertion.type == "equals":
                return payload == str(assertion.value)

        if assertion.type in {"contains", "includes"}:
            return str(assertion.value) in output
        elif assertion.type == "not_contains":
            return str(assertion.value) not in output
        elif assertion.type == "regex":
            return bool(re.search(str(assertion.value), output))
        elif assertion.type == "max_length":
            return len(output) <= int(assertion.value)
        elif assertion.type == "min_length":
            return len(output) >= int(assertion.value)
        elif assertion.type == "equals":
            return output == str(assertion.value)
        elif assertion.type == "json_schema":
            # Basic validation that it IS json
            try:
                parsed = orjson.loads(output)
                # Validate against schema if value is provided and not a simple True boolean
                if isinstance(assertion.value, dict) or assertion.value is False:
                    jsonschema.validate(instance=parsed, schema=assertion.value)
                return True
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
