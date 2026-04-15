import pytest
from pydantic import ValidationError

from app.testing.models import Assertion, TestCase, TestSuite, TestResult, SuiteResult


def test_assertion_model_valid():
    """Test creating a valid Assertion model."""
    assertion = Assertion(type="contains", value="test string")
    assert assertion.type == "contains"
    assert assertion.target == "output"  # Default value
    assert assertion.value == "test string"
    assert assertion.threshold is None
    assert assertion.error_message is None

    assertion_with_target = Assertion(
        type="regex",
        target="ir",
        value=r"^\d+$",
        threshold=0.9,
        error_message="Must be a number",
    )
    assert assertion_with_target.type == "regex"
    assert assertion_with_target.target == "ir"
    assert assertion_with_target.value == r"^\d+$"
    assert assertion_with_target.threshold == 0.9
    assert assertion_with_target.error_message == "Must be a number"


def test_assertion_model_invalid_type():
    """Test creating an Assertion model with an invalid type."""
    with pytest.raises(ValidationError) as exc_info:
        Assertion(type="invalid_type", value="test")
    assert "type" in str(exc_info.value)


def test_testcase_model_valid():
    """Test creating a valid TestCase model."""
    assertion1 = Assertion(type="contains", value="success")
    test_case = TestCase(
        id="tc-001",
        description="A sample test case",
        input_variables={"var1": "value1"},
        assertions=[assertion1],
        model="gpt-4",
        temperature=0.7,
    )
    assert test_case.id == "tc-001"
    assert test_case.description == "A sample test case"
    assert test_case.input_variables == {"var1": "value1"}
    assert len(test_case.assertions) == 1
    assert test_case.assertions[0].type == "contains"
    assert test_case.model == "gpt-4"
    assert test_case.temperature == 0.7


def test_testsuite_model_valid():
    """Test creating a valid TestSuite model."""
    test_case1 = TestCase(id="tc-1")
    test_case2 = TestCase(id="tc-2")

    suite = TestSuite(
        name="Main Suite",
        description="Test suite for main prompt",
        prompt_file="prompts/main.txt",
        defaults={"global_var": "default"},
        test_cases=[test_case1, test_case2],
    )
    assert suite.name == "Main Suite"
    assert suite.description == "Test suite for main prompt"
    assert suite.prompt_file == "prompts/main.txt"
    assert suite.defaults == {"global_var": "default"}
    assert len(suite.test_cases) == 2


def test_testresult_model_valid():
    """Test creating a valid TestResult model."""
    result = TestResult(
        test_case_id="tc-001",
        passed=True,
        output="Generated output text",
        duration_ms=150.5,
    )
    assert result.test_case_id == "tc-001"
    assert result.passed is True
    assert result.output == "Generated output text"
    assert result.duration_ms == 150.5
    assert result.failures == []
    assert result.error is None

    failed_result = TestResult(
        test_case_id="tc-002",
        passed=False,
        output="Bad output",
        duration_ms=200.0,
        failures=["Expected 'good', got 'bad'"],
        error="Connection Timeout",
    )
    assert failed_result.passed is False
    assert len(failed_result.failures) == 1
    assert failed_result.error == "Connection Timeout"


def test_suiteresult_model_valid():
    """Test creating a valid SuiteResult model."""
    t_res1 = TestResult(test_case_id="t1", passed=True, output="ok", duration_ms=10)
    t_res2 = TestResult(
        test_case_id="t2", passed=False, output="fail", duration_ms=20, failures=["f1"]
    )

    suite_result = SuiteResult(
        suite_name="Suite A",
        passed=1,
        failed=1,
        errors=0,
        total_duration_ms=30.0,
        results=[t_res1, t_res2],
    )
    assert suite_result.suite_name == "Suite A"
    assert suite_result.passed == 1
    assert suite_result.failed == 1
    assert suite_result.errors == 0
    assert suite_result.total_duration_ms == 30.0
    assert len(suite_result.results) == 2
