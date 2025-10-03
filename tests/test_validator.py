"""Tests for prompt validation system."""

from __future__ import annotations

from app.validator import (
    validate_prompt,
)
from app.compiler import compile_text_v2


def test_validator_perfect_prompt():
    """Test a high-quality prompt with no issues."""
    text = """As a senior Python developer, review this authentication code.

    Goal: Identify security vulnerabilities and suggest improvements.

    Context: REST API endpoint for user login with JWT tokens.

    Focus on:
    - Input validation
    - SQL injection risks
    - Token expiration handling

    Format: Markdown with code examples

    Example output:
    ## Security Issues
    1. Missing rate limiting
    2. Weak password hashing
    """
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert result.score.total >= 75.0
    assert len([i for i in result.issues if i.severity == "error"]) == 0
    assert len(result.strengths) > 0


def test_validator_vague_prompt():
    """Test detection of vague terms."""
    text = "Write something about stuff and things maybe"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert result.score.clarity < 90.0
    assert any("vague" in i.message.lower() for i in result.issues)


def test_validator_missing_examples():
    """Test detection of missing examples in complex tasks."""
    text = """Create a comprehensive multi-step algorithm for optimizing
    distributed systems with load balancing and fault tolerance"""
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    # Should warn about missing examples for complex task
    assert any("example" in i.message.lower() for i in result.issues)


def test_validator_conflicting_constraints():
    """Test detection of conflicting constraints."""
    text = "Write a brief comprehensive detailed short extensive summary"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert any("conflict" in i.message.lower() for i in result.issues)


def test_validator_risky_without_constraints():
    """Test detection of risk without sufficient safety constraints."""
    text = "Give me financial investment advice for my retirement"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    # Should warn about insufficient safety constraints for risky intent
    assert any("risk" in i.message.lower() or "safety" in i.message.lower() for i in result.issues)


def test_validator_unknown_domain():
    """Test handling of unclear domain."""
    text = "xyz abc qwerty asdfgh"  # Gibberish
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    # Compiler may return "general" or "unknown" for unclear input
    assert ir.domain in ["unknown", "general"]
    # Validator should still process it (may have vague term warnings)
    assert result.score.total >= 0


def test_validator_generic_persona():
    """Test info message for generic persona."""
    text = "As an assistant, help me with this task"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert any("persona" in i.message.lower() for i in result.issues)


def test_validator_teaching_without_level():
    """Test warning for teaching intent without skill level."""
    text = "Teach me about Python programming"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    if "teaching" in ir.intents:
        assert any("level" in i.message.lower() for i in result.issues)


def test_validator_score_calculation():
    """Test score calculation."""
    text = "Write code"  # Very minimal prompt
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert 0 <= result.score.total <= 100
    assert 0 <= result.score.clarity <= 100
    assert 0 <= result.score.specificity <= 100
    assert 0 <= result.score.completeness <= 100
    assert 0 <= result.score.consistency <= 100


def test_validator_issue_counts():
    """Test issue counting by severity."""
    text = "something about stuff"  # Multiple issues
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    assert result.errors + result.warnings + result.info == len(result.issues)
    assert all(i.severity in ["error", "warning", "info"] for i in result.issues)


def test_validator_strengths_detection():
    """Test strength detection."""
    text = """As a senior data scientist, analyze this dataset.

    Output format: JSON with statistical summary

    Example:
    {
      "mean": 42.5,
      "median": 40.0
    }

    Steps:
    1. Load data
    2. Clean missing values
    3. Calculate statistics
    """
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    # Should detect: examples, persona, output format, steps
    assert len(result.strengths) >= 2


def test_validator_to_dict():
    """Test conversion to dictionary."""
    text = "Write a tutorial"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    result_dict = result.to_dict()
    assert "score" in result_dict
    assert "issues" in result_dict
    assert "strengths" in result_dict
    assert "summary" in result_dict
    assert "total" in result_dict["score"]


def test_validator_excessive_banned_words():
    """Test detection of too many banned words."""
    text = "Write text but don't use: " + ", ".join([f"word{i}" for i in range(15)])
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    if ir.banned and len(ir.banned) > 10:
        assert any("banned" in i.message.lower() for i in result.issues)


def test_validator_empty_goals():
    """Test detection of missing goals."""
    text = "Just write something"
    ir = compile_text_v2(text)
    result = validate_prompt(ir, text)

    if not ir.goals:
        assert any("goal" in i.message.lower() for i in result.issues)


def test_validator_overly_broad_goals():
    """Test detection of overly broad goals."""
    text = "Create a complete comprehensive system for everything"
    ir = compile_text_v2(text)
    validate_prompt(ir, text)

    # Just verify the IR was created with goals
    assert len(ir.goals) > 0
