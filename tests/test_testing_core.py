
import pytest
from pathlib import Path
from app.testing.models import TestSuite, TestCase, Assertion
from app.testing.runner import TestRunner, MockExecutor, Executor

class CustomMockExecutor(Executor):
    def execute(self, prompt: str, config: dict) -> str:
        if "fail" in prompt:
            return "This response fails criteria"
        return "{\"key\": \"top_level_value\", \"nested\": {\"key\": \"value\"}}"

def test_runner_basic_flow(tmp_path):
    # 1. underlying prompt file
    p_file = tmp_path / "test_prompt.txt"
    p_file.write_text("Hello {{name}}, please make me a {{thing}}.", encoding="utf-8")
    
    # 2. Define Suite
    suite = TestSuite(
        name="Demo Suite",
        prompt_file=str(p_file.name),
        defaults={"name": "User"},
        test_cases=[
            TestCase(
                id="c1",
                input_variables={"thing": "sandwich"},
                assertions=[

                    Assertion(type="json_schema", value=True),
                    Assertion(type="not_contains", value="fail")
                ]
            ),
            TestCase(
                id="c2",
                input_variables={"thing": "fail"}, # Triggers mock failure
                assertions=[
                     Assertion(type="not_contains", value="fails") 
                ]
            )
        ]
    )
    
    # 3. Run
    runner = TestRunner(executor=CustomMockExecutor())
    result = runner.run_suite(suite, base_dir=tmp_path)
    
    assert result.passed == 1
    assert result.failed == 1
    assert result.errors == 0
    
    # Check Case 1 (Pass)
    r1 = next(r for r in result.results if r.test_case_id == "c1")
    assert r1.passed
    assert "top_level_value" in r1.output
    
    # Check Case 2 (Fail)
    r2 = next(r for r in result.results if r.test_case_id == "c2")
    assert not r2.passed
    assert len(r2.failures) == 1
    assert "Assertion failed: not_contains fails" in r2.failures[0]

def test_runner_missing_file(tmp_path):
    suite = TestSuite(
        name="Bad File",
        prompt_file="missing.txt",
        test_cases=[TestCase(id="c1")]
    )
    runner = TestRunner()
    result = runner.run_suite(suite, base_dir=tmp_path)
    
    assert result.errors == 0 
    assert result.failed == 1
    # Actually my logic sets "errors=0" but sets individual result error?
    # Let's check logic: "Fail everything if prompt is missing" -> failed=len, passed=0
    # Wait, code said: results=[ErrorResult...], failed=length. So yes.
    
    assert result.results[0].error is not None
    assert "not found" in result.results[0].error
