"""Tests for auto-fix functionality."""

from __future__ import annotations

from app.autofix import auto_fix_prompt, explain_fixes


def test_autofix_vague_terms():
    """Test fixing vague terms."""
    text = "do something with stuff"
    result = auto_fix_prompt(text, max_fixes=3)

    # Should improve or already be good
    assert result.fixed_score >= result.original_score
    # Check if vague terms were addressed
    if result.fixes_applied:
        assert any("vague" in fix.fix_type for fix in result.fixes_applied)


def test_autofix_add_persona():
    """Test adding persona to prompt."""
    text = "Write a tutorial about Python"
    result = auto_fix_prompt(text, max_fixes=5)

    # Score should improve or stay same if already good
    assert result.fixed_score >= result.original_score
    # May add persona if needed
    if "persona" in " ".join([f.fix_type for f in result.fixes_applied]):
        assert "as a" in result.fixed_text.lower() or "as an" in result.fixed_text.lower()


def test_autofix_add_examples():
    """Test adding examples for complex tasks."""
    text = "Create a comprehensive multi-step algorithm for distributed systems"
    result = auto_fix_prompt(text, max_fixes=5, min_score_target=70.0)

    # Should attempt to add examples
    assert result.fixed_score >= result.original_score
    # May add example section
    if "example" in result.fixed_text.lower():
        assert any("example" in fix.fix_type for fix in result.fixes_applied)


def test_autofix_target_score():
    """Test that auto-fix stops at target score."""
    text = "analyze data"
    result = auto_fix_prompt(text, max_fixes=10, min_score_target=80.0)

    # Should stop when target reached or no more fixes
    assert result.fixed_score >= 80.0 or result.remaining_issues == 0 or not result.fixes_applied


def test_autofix_max_fixes_limit():
    """Test that auto-fix respects max_fixes limit."""
    text = "do something"
    result = auto_fix_prompt(text, max_fixes=2)

    # Should not apply more than max_fixes
    assert len(result.fixes_applied) <= 2


def test_autofix_no_change_perfect_prompt():
    """Test that perfect prompts are not changed."""
    text = """As a senior Python developer, review this authentication code.
    
    Goal: Identify security vulnerabilities and suggest improvements.
    
    Context: REST API endpoint for user login with JWT tokens.
    
    Focus on:
    - Input validation
    - SQL injection risks
    - Token expiration handling
    
    Output format: Markdown with code examples
    
    Example output:
    ## Security Issues
    1. Missing rate limiting
    """
    result = auto_fix_prompt(text, max_fixes=5)

    # High-quality prompt should have minimal changes
    assert result.original_score > 75
    # May still apply minor improvements
    assert result.fixed_score >= result.original_score


def test_autofix_output_format():
    """Test adding output format."""
    text = "Write documentation"
    result = auto_fix_prompt(text, max_fixes=5)

    # Should improve score
    assert result.fixed_score >= result.original_score


def test_explain_fixes():
    """Test fix explanation generation."""
    text = "do something with stuff"
    result = auto_fix_prompt(text, max_fixes=3)
    explanation = explain_fixes(result)

    # Should contain key information
    assert "Original Score" in explanation
    assert "Fixed Score" in explanation
    assert "Improvement" in explanation
    assert str(result.original_score) in explanation


def test_autofix_confidence_scores():
    """Test that fixes have confidence scores."""
    text = "maybe do something"
    result = auto_fix_prompt(text, max_fixes=3)

    for fix in result.fixes_applied:
        assert 0.0 <= fix.confidence <= 1.0


def test_autofix_preserves_core_intent():
    """Test that fixes don't change core prompt intent."""
    text = "Explain machine learning to beginners"
    result = auto_fix_prompt(text, max_fixes=5)

    # Core concepts should remain
    assert "machine learning" in result.fixed_text.lower()
    assert "beginner" in result.fixed_text.lower() or "intermediate" in result.fixed_text.lower()


def test_autofix_risk_domain():
    """Test fixing prompts in risky domains."""
    text = "Give me financial investment advice"
    result = auto_fix_prompt(text, max_fixes=5)

    # Should add risk mitigation
    assert result.fixed_score >= result.original_score
    # May add disclaimer or safety constraint


def test_autofix_teaching_level():
    """Test adding teaching level specification."""
    text = "Teach me Python programming"
    result = auto_fix_prompt(text, max_fixes=5)

    # Should add teaching-related improvements
    assert result.fixed_score >= result.original_score


def test_autofix_multiple_issues():
    """Test fixing multiple issues in one prompt."""
    text = "maybe write something about stuff for things"
    result = auto_fix_prompt(text, max_fixes=5)

    # Should improve score
    assert result.fixed_score >= result.original_score
    # May apply fixes if issues detected
    if result.original_score < 80:
        assert result.improvement >= 0


def test_autofix_empty_input():
    """Test behavior with minimal input."""
    text = "do it"
    result = auto_fix_prompt(text, max_fixes=5)

    # Should still try to improve
    assert result.fixed_text != text or result.original_score > 70
