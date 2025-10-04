"""Automatic prompt fixing based on validation issues.

Applies intelligent fixes to prompts based on validator feedback.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from app.models_v2 import IRv2
from app.compiler import compile_text_v2
from app.validator import ValidationResult, validate_prompt


@dataclass
class AutoFix:
    """A single automatic fix."""

    issue_id: int  # Index in validation issues list
    original_text: str
    fixed_text: str
    fix_type: str  # "replace_vague", "add_persona", "add_examples", etc.
    description: str
    confidence: float  # 0.0-1.0, how confident we are in this fix


@dataclass
class AutoFixResult:
    """Result of automatic fixing."""

    original_text: str
    fixed_text: str
    original_score: float
    fixed_score: float
    improvement: float
    fixes_applied: List[AutoFix]
    remaining_issues: int


# Vague term replacements
VAGUE_REPLACEMENTS: Dict[str, List[str]] = {
    "something": ["a specific component", "a particular feature", "a concrete example"],
    "anything": ["any specific item", "a particular element"],
    "stuff": ["data", "content", "information", "elements"],
    "things": ["items", "elements", "components", "features"],
    "somehow": ["through a specific method", "using a particular approach"],
    "maybe": ["optionally", "if applicable", "when relevant"],
    "probably": ["likely", "typically", "generally"],
    "might": ["could", "may"],
}

# Generic persona improvements
PERSONA_SUGGESTIONS: Dict[str, str] = {
    "general": "expert consultant",
    "technology": "senior software engineer",
    "business": "business analyst",
    "science": "research scientist",
    "education": "experienced educator",
    "medical": "medical professional",
    "financial": "financial analyst",
    "legal": "legal consultant",
    "marketing": "marketing strategist",
    "design": "UX/UI designer",
    "data": "senior data scientist",
    "ai": "AI/ML engineer",
    "security": "security specialist",
}

# Domain-specific example templates
EXAMPLE_TEMPLATES: Dict[str, List[str]] = {
    "technology": [
        "For example: Implementing a REST API endpoint with authentication",
        "Example use case: Microservices architecture with Docker containers",
    ],
    "business": [
        "For example: Q4 revenue analysis with year-over-year comparison",
        "Example scenario: Customer retention strategy implementation",
    ],
    "education": [
        "For example: Teaching Python basics to beginners with hands-on exercises",
        "Example lesson: Explaining loops with real-world analogies",
    ],
    "data": [
        "For example: Analyzing sales data to identify trends",
        "Example output: Statistical summary with visualization recommendations",
    ],
    "writing": [
        "For example: Technical blog post about cloud migration",
        "Example format: Tutorial with code snippets and explanations",
    ],
}


def _replace_vague_terms(text: str) -> Tuple[str, List[str]]:
    """Replace vague terms with specific alternatives.

    Returns:
        (fixed_text, list_of_changes)
    """
    fixed = text
    changes = []

    for vague, replacements in VAGUE_REPLACEMENTS.items():
        # Case-insensitive search
        pattern = re.compile(r"\b" + re.escape(vague) + r"\b", re.IGNORECASE)
        matches = pattern.findall(fixed)

        if matches:
            # Use first replacement suggestion
            replacement = replacements[0]
            fixed = pattern.sub(replacement, fixed, count=1)  # Fix first occurrence
            changes.append(f"'{matches[0]}' → '{replacement}'")

    return fixed, changes


def _add_persona_prefix(text: str, domain: str) -> Tuple[str, str]:
    """Add persona prefix to prompt.

    Returns:
        (fixed_text, added_persona)
    """
    # Check if already has persona marker
    persona_markers = ["as a", "as an", "you are", "act as", "role:"]
    if any(marker in text.lower()[:50] for marker in persona_markers):
        return text, ""

    # Get suggested persona
    persona = PERSONA_SUGGESTIONS.get(domain, "experienced professional")

    # Add persona prefix
    fixed = f"As a {persona}, {text[0].lower()}{text[1:]}"
    return fixed, persona


def _add_example_section(text: str, domain: str) -> Tuple[str, str]:
    """Add example section to prompt.

    Returns:
        (fixed_text, added_example)
    """
    # Check if already has examples
    example_markers = ["example:", "for example", "e.g.", "such as"]
    if any(marker in text.lower() for marker in example_markers):
        return text, ""

    # Get domain-specific example
    examples = EXAMPLE_TEMPLATES.get(domain, EXAMPLE_TEMPLATES["technology"])
    example = examples[0]

    # Add example section
    fixed = f"{text}\n\n{example}"
    return fixed, example


def _add_output_format(text: str) -> Tuple[str, str]:
    """Add output format specification.

    Returns:
        (fixed_text, added_format)
    """
    # Check if already has format
    format_markers = ["format:", "output:", "response format", "structure:"]
    if any(marker in text.lower() for marker in format_markers):
        return text, ""

    # Add format specification
    format_spec = "Output format: Markdown with clear sections"
    fixed = f"{text}\n\n{format_spec}"
    return fixed, format_spec


def _add_constraints(text: str, constraint_type: str) -> Tuple[str, str]:
    """Add specific constraints.

    Returns:
        (fixed_text, added_constraint)
    """
    constraints = {
        "risk": "Note: Provide general information only, not professional advice",
        "teaching": "Target audience: Intermediate level with step-by-step explanations",
        "complexity": "Include practical examples to illustrate concepts",
    }

    constraint = constraints.get(constraint_type, "")
    if not constraint:
        return text, ""

    fixed = f"{text}\n\nConstraint: {constraint}"
    return fixed, constraint


def auto_fix_prompt(
    text: str, max_fixes: int = 5, min_score_target: float = 75.0
) -> AutoFixResult:
    """Automatically fix prompt based on validation issues.

    Args:
        text: Original prompt text
        max_fixes: Maximum number of fixes to apply
        min_score_target: Stop when score reaches this threshold

    Returns:
        AutoFixResult with original/fixed text and improvement metrics
    """
    original_text = text
    fixed_text = text
    applied_fixes: List[AutoFix] = []

    # Initial validation
    original_ir = compile_text_v2(original_text)
    original_result = validate_prompt(original_ir, original_text)
    original_score = original_result.score.total

    # Try to fix issues
    for fix_attempt in range(max_fixes):
        # Re-compile and validate current version
        current_ir = compile_text_v2(fixed_text)
        current_result = validate_prompt(current_ir, fixed_text)
        current_score = current_result.score.total

        # Check if we reached target
        if current_score >= min_score_target:
            break

        # No more issues to fix
        if not current_result.issues:
            break

        # Find fixable issue
        fixed_this_round = False
        for issue_idx, issue in enumerate(current_result.issues):
            fix_applied = False
            fix_description = ""
            new_text = fixed_text
            fix_type = ""

            # Fix vague terms - check actual text, not just IR
            if "vague" in issue.message.lower() or any(
                term in fixed_text.lower() for term in ["something", "stuff", "maybe", "probably"]
            ):
                new_text, changes = _replace_vague_terms(fixed_text)
                if changes:
                    fix_applied = True
                    fix_type = "replace_vague"
                    fix_description = f"Replaced vague terms: {', '.join(changes)}"

            # Add persona - be more aggressive
            elif (
                "persona" in issue.message.lower()
                or (issue.field and "persona" in issue.field)
                or current_ir.persona == "assistant"
            ):
                new_text, persona = _add_persona_prefix(fixed_text, current_ir.domain)
                if persona:
                    fix_applied = True
                    fix_type = "add_persona"
                    fix_description = f"Added persona: '{persona}'"

            # Add examples
            elif "example" in issue.message.lower():
                new_text, example = _add_example_section(fixed_text, current_ir.domain)
                if example:
                    fix_applied = True
                    fix_type = "add_examples"
                    fix_description = f"Added example section"

            # Add output format
            elif "output format" in issue.message.lower():
                new_text, format_spec = _add_output_format(fixed_text)
                if format_spec:
                    fix_applied = True
                    fix_type = "add_format"
                    fix_description = f"Added output format specification"

            # Add constraints for risky domains
            elif "risk" in issue.message.lower():
                new_text, constraint = _add_constraints(fixed_text, "risk")
                if constraint:
                    fix_applied = True
                    fix_type = "add_risk_constraint"
                    fix_description = "Added risk mitigation constraint"

            # Add teaching level
            elif "teaching" in issue.message.lower() and "level" in issue.message.lower():
                new_text, constraint = _add_constraints(fixed_text, "teaching")
                if constraint:
                    fix_applied = True
                    fix_type = "add_teaching_level"
                    fix_description = "Added teaching level specification"

            # Add examples for complexity
            elif "complex" in issue.message.lower():
                new_text, constraint = _add_constraints(fixed_text, "complexity")
                if constraint:
                    fix_applied = True
                    fix_type = "add_complexity_help"
                    fix_description = "Added complexity guidance"

            if fix_applied:
                # Calculate confidence based on score improvement potential
                confidence = min(issue.score_impact / 20.0, 1.0)

                applied_fixes.append(
                    AutoFix(
                        issue_id=issue_idx,
                        original_text=fixed_text,
                        fixed_text=new_text,
                        fix_type=fix_type,
                        description=fix_description,
                        confidence=confidence,
                    )
                )

                fixed_text = new_text
                fixed_this_round = True
                break  # Apply one fix at a time

        if not fixed_this_round:
            break  # No more fixable issues

    # Final validation
    final_ir = compile_text_v2(fixed_text)
    final_result = validate_prompt(final_ir, fixed_text)
    final_score = final_result.score.total

    return AutoFixResult(
        original_text=original_text,
        fixed_text=fixed_text,
        original_score=original_score,
        fixed_score=final_score,
        improvement=final_score - original_score,
        fixes_applied=applied_fixes,
        remaining_issues=len(final_result.issues),
    )


def explain_fixes(result: AutoFixResult) -> str:
    """Generate human-readable explanation of applied fixes.

    Args:
        result: AutoFixResult to explain

    Returns:
        Formatted explanation text
    """
    lines = []
    lines.append("=== Auto-Fix Report ===\n")
    lines.append(f"Original Score: {result.original_score:.1f}/100")
    lines.append(f"Fixed Score:    {result.fixed_score:.1f}/100")
    lines.append(
        f"Improvement:    +{result.improvement:.1f} ({result.improvement/result.original_score*100:.1f}%)\n"
    )

    if result.fixes_applied:
        lines.append(f"Applied {len(result.fixes_applied)} fix(es):\n")
        for i, fix in enumerate(result.fixes_applied, 1):
            lines.append(f"{i}. [{fix.fix_type}] {fix.description}")
            lines.append(f"   Confidence: {fix.confidence:.0%}")

    if result.remaining_issues > 0:
        lines.append(f"\n⚠ {result.remaining_issues} issue(s) remaining (may need manual review)")
    else:
        lines.append("\n✓ All issues resolved!")

    return "\n".join(lines)


__all__ = [
    "AutoFix",
    "AutoFixResult",
    "auto_fix_prompt",
    "explain_fixes",
]
