from __future__ import annotations
from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field


class Assertion(BaseModel):
    """A single assertion to run against the output."""

    type: Literal["contains", "not_contains", "regex", "max_length", "min_length", "json_schema"]
    value: Union[str, int, float, Dict[str, Any]]
    threshold: Optional[float] = None  # For similarity or fuzzy matching if added later
    error_message: Optional[str] = None


class TestCase(BaseModel):
    """A test case definition."""

    id: str
    description: Optional[str] = None
    input_variables: Dict[str, Any] = Field(default_factory=dict)
    assertions: List[Assertion] = Field(default_factory=list)
    # Optional LLM config overrides for this specific test
    model: Optional[str] = None
    temperature: Optional[float] = None


class TestSuite(BaseModel):
    """A collection of test cases for a specific prompt template."""

    name: str
    description: Optional[str] = None
    prompt_file: str  # Path to the prompt file being tested (relative to suite or absolute)
    defaults: Dict[str, Any] = Field(default_factory=dict)  # Default input vars
    test_cases: List[TestCase]


class TestResult(BaseModel):
    """Result of a single test case execution."""

    test_case_id: str
    passed: bool
    output: str
    duration_ms: float
    failures: List[str] = Field(default_factory=list)
    error: Optional[str] = None  # For system errors (not assertion failures)


class SuiteResult(BaseModel):
    """Result of a full suite execution."""

    suite_name: str
    passed: int
    failed: int
    errors: int
    total_duration_ms: float
    results: List[TestResult]
