"""Prompt validation and quality scoring system.

Analyzes compiled IR to detect quality issues, missing elements,
anti-patterns, and provides actionable suggestions for improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.models_v2 import IRv2


@dataclass
class ValidationIssue:
    """A single validation issue or warning."""

    severity: str  # "error", "warning", "info"
    category: str  # "clarity", "specificity", "completeness", "consistency"
    message: str
    suggestion: str
    field: Optional[str] = None  # IR field that triggered the issue
    score_impact: float = 0.0  # How much this affects the quality score (0-100)


@dataclass
class QualityScore:
    """Quality score breakdown."""

    total: float  # 0-100
    clarity: float  # 0-100
    specificity: float  # 0-100
    completeness: float  # 0-100
    consistency: float  # 0-100


@dataclass
class ValidationResult:
    """Complete validation result."""

    score: QualityScore
    issues: List[ValidationIssue] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    info: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": {
                "total": round(self.score.total, 1),
                "clarity": round(self.score.clarity, 1),
                "specificity": round(self.score.specificity, 1),
                "completeness": round(self.score.completeness, 1),
                "consistency": round(self.score.consistency, 1),
            },
            "issues": [
                {
                    "severity": issue.severity,
                    "category": issue.category,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                    "field": issue.field,
                }
                for issue in self.issues
            ],
            "strengths": self.strengths,
            "summary": {
                "errors": self.errors,
                "warnings": self.warnings,
                "info": self.info,
            },
        }


class PromptValidator:
    """Validates compiled prompts and provides quality scores."""

    # Anti-pattern keywords
    VAGUE_TERMS = {
        "something",
        "anything",
        "stuff",
        "things",
        "etc",
        "whatever",
        "somehow",
        "maybe",
        "probably",
        "might",
    }

    OVERLY_BROAD = {
        "everything",
        "all",
        "any",
        "complete",
        "comprehensive",
        "full",
        "entire",
        "total",
    }

    CONFLICTING_PAIRS = [
        (["brief", "short", "concise"], ["detailed", "comprehensive", "extensive"]),
        (["formal", "professional"], ["casual", "informal"]),
        (["simple", "basic"], ["advanced", "complex", "sophisticated"]),
    ]

    def __init__(self):
        """Initialize validator."""
        pass

    def validate(self, ir: IRv2, original_text: Optional[str] = None) -> ValidationResult:
        """Validate an IR and return quality score + issues.

        Args:
            ir: Compiled IR v2 to validate
            original_text: Original prompt text (optional, for additional analysis)

        Returns:
            ValidationResult with score and issues
        """
        issues: List[ValidationIssue] = []
        strengths: List[str] = []

        # Run all validation checks
        issues.extend(self._check_clarity(ir, original_text))
        issues.extend(self._check_specificity(ir))
        issues.extend(self._check_completeness(ir))
        issues.extend(self._check_consistency(ir))
        issues.extend(self._check_anti_patterns(ir, original_text))

        # Identify strengths
        strengths.extend(self._identify_strengths(ir))

        # Calculate scores
        score = self._calculate_score(ir, issues)

        # Count by severity
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        info = sum(1 for i in issues if i.severity == "info")

        return ValidationResult(
            score=score,
            issues=issues,
            strengths=strengths,
            errors=errors,
            warnings=warnings,
            info=info,
        )

    def _check_clarity(
        self, ir: IRv2, original_text: Optional[str] = None
    ) -> List[ValidationIssue]:
        """Check for clarity issues."""
        issues = []

        # Check for vague terms in original text
        if original_text:
            text_lower = original_text.lower()
            found_vague = [term for term in self.VAGUE_TERMS if term in text_lower.split()]
            if found_vague:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="clarity",
                        message=f"Vague terms detected: {', '.join(found_vague[:3])}",
                        suggestion="Replace vague terms with specific details. E.g., 'something' → 'a REST API endpoint'",
                        score_impact=5.0 * len(found_vague),
                    )
                )

        # Check if persona is generic
        if ir.persona and ir.persona in ["assistant", "helper", "ai"]:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="clarity",
                    message="Generic persona detected",
                    suggestion="Consider a more specific persona (e.g., 'senior python developer', 'technical writer')",
                    field="persona",
                    score_impact=3.0,
                )
            )

        # Check for ambiguous metadata
        ambiguous = ir.metadata.get("ambiguous_terms", []) if isinstance(ir.metadata, dict) else []
        if ambiguous and len(ambiguous) > 5:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="clarity",
                    message=f"{len(ambiguous)} ambiguous terms detected",
                    suggestion="Clarify ambiguous terms or provide context",
                    field="metadata.ambiguous_terms",
                    score_impact=2.0 * min(len(ambiguous), 10),
                )
            )

        return issues

    def _check_specificity(self, ir: IRv2) -> List[ValidationIssue]:
        """Check for specificity issues."""
        issues = []

        # Check if domain is unknown
        if ir.domain == "unknown":
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="specificity",
                    message="Domain could not be detected",
                    suggestion="Add context about the subject area (e.g., 'for a Python project', 'in healthcare')",
                    field="domain",
                    score_impact=10.0,
                )
            )

        # Check for missing role
        if not ir.role or len(ir.role.strip()) < 10:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="specificity",
                    message="Role is missing or too brief",
                    suggestion="Specify the role or context (e.g., 'as a code reviewer for a team project')",
                    field="role",
                    score_impact=5.0,
                )
            )

        # Check for overly broad goals
        if ir.goals:
            for goal in ir.goals[:3]:  # Check first 3 goals
                if any(broad in goal.lower() for broad in self.OVERLY_BROAD):
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            category="specificity",
                            message=f"Goal may be too broad: '{goal[:50]}...'",
                            suggestion="Break down broad goals into specific, measurable objectives",
                            field="goals",
                            score_impact=3.0,
                        )
                    )
                    break  # Only warn once

        return issues

    def _check_completeness(self, ir: IRv2) -> List[ValidationIssue]:
        """Check for missing important elements."""
        issues = []

        # Check for missing examples when task seems complex (multi-step, algorithm, etc.)
        complexity = ir.metadata.get("complexity_score", 0.0) if isinstance(ir.metadata, dict) else 0.0
        task_text = " ".join(ir.goals + ir.tasks).lower()
        complex_keywords = ["multi-step", "algorithm", "comprehensive", "complex", "advanced", "distributed"]
        is_complex = complexity > 0.6 or any(kw in task_text for kw in complex_keywords)
        
        if not ir.examples and is_complex:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="completeness",
                    message="Complex task without examples",
                    suggestion="Add examples to clarify expected output format",
                    field="examples",
                    score_impact=15.0,
                )
            )

        # Check for missing constraints in risky domains
        risk_flags = ir.metadata.get("risk_flags", []) if isinstance(ir.metadata, dict) else []
        has_risk_intent = "risk" in ir.intents if ir.intents else False
        
        if (risk_flags or has_risk_intent) and len(ir.constraints) < 2:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="completeness",
                    message="Risk detected but insufficient safety constraints",
                    suggestion="Add explicit safety constraints for risk mitigation (e.g., disclaimers, verification steps, limitations)",
                    field="constraints",
                    score_impact=15.0,
                )
            )

        # Check for missing output format specification
        if not ir.output_format or ir.output_format == "text":
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="completeness",
                    message="Output format not specified",
                    suggestion="Specify desired format (e.g., 'markdown', 'json', 'bullet points')",
                    field="output_format",
                    score_impact=5.0,
                )
            )

        # Check for teaching intent without level
        if (
            ir.intents
            and "teaching" in ir.intents
            and not any(c.id.startswith("level_") for c in ir.constraints)
        ):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="completeness",
                    message="Teaching intent without skill level",
                    suggestion="Specify target audience level (beginner/intermediate/advanced)",
                    field="intents",
                    score_impact=10.0,
                )
            )

        return issues

    def _check_consistency(self, ir: IRv2) -> List[ValidationIssue]:
        """Check for internal consistency issues."""
        issues = []

        # Check for conflicting constraints and goals
        constraint_texts = [c.text.lower() for c in ir.constraints]
        goal_texts = [g.lower() for g in ir.goals]
        all_text = " ".join(constraint_texts + goal_texts)

        for set_a, set_b in self.CONFLICTING_PAIRS:
            found_a = any(term in all_text for term in set_a)
            found_b = any(term in all_text for term in set_b)
            if found_a and found_b:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="consistency",
                        message=f"Potentially conflicting constraints: {set_a[0]} vs {set_b[0]}",
                        suggestion="Review constraints for conflicts and prioritize one direction",
                        field="constraints",
                        score_impact=10.0,
                    )
                )

        # Check tone vs persona consistency
        if ir.tone and ir.persona:
            tone_text = " ".join(ir.tone).lower()
            if "formal" in tone_text and any(
                casual in ir.persona.lower() for casual in ["friend", "buddy", "casual"]
            ):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="consistency",
                        message="Tone and persona mismatch",
                        suggestion="Align tone (formal) with persona or vice versa",
                        field="tone",
                        score_impact=5.0,
                    )
                )

        return issues

    def _check_anti_patterns(
        self, ir: IRv2, original_text: Optional[str] = None
    ) -> List[ValidationIssue]:
        """Check for common anti-patterns."""
        issues = []

        # Check for missing persona entirely
        if not ir.persona or ir.persona == "assistant":
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="completeness",
                    message="No explicit persona defined",
                    suggestion="Define a persona to get more targeted responses (e.g., 'expert data scientist')",
                    field="persona",
                    score_impact=5.0,
                )
            )

        # Check for empty goals
        if not ir.goals or len(ir.goals) == 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="completeness",
                    message="No clear goals defined",
                    suggestion="State explicit goals or objectives for the task",
                    field="goals",
                    score_impact=15.0,
                )
            )

        # Check for excessive banned words (over-constraining)
        if ir.banned and len(ir.banned) > 10:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="specificity",
                    message=f"Many banned words ({len(ir.banned)})",
                    suggestion="Too many constraints can limit creativity; focus on the most important ones",
                    field="banned",
                    score_impact=3.0,
                )
            )

        return issues

    def _identify_strengths(self, ir: IRv2) -> List[str]:
        """Identify strong points in the prompt."""
        strengths = []

        if ir.examples and len(ir.examples) > 0:
            strengths.append(f"Includes {len(ir.examples)} example(s) for clarity")

        if ir.persona and ir.persona not in ["assistant", "helper", "ai"]:
            strengths.append(f"Well-defined persona: '{ir.persona}'")

        if ir.constraints and len(ir.constraints) >= 3:
            strengths.append(f"Clear constraints ({len(ir.constraints)} defined)")

        if ir.output_format and ir.output_format != "text":
            strengths.append(f"Specific output format: {ir.output_format}")

        if ir.steps and len(ir.steps) > 0:
            strengths.append(f"Structured approach with {len(ir.steps)} steps")

        domain_conf = ir.metadata.get("domain_confidence", {}) if isinstance(ir.metadata, dict) else {}
        if isinstance(domain_conf, dict) and domain_conf.get("ratio", 0.0) > 0.7:
            strengths.append(f"Strong domain clarity: {ir.domain}")

        return strengths

    def _calculate_score(self, ir: IRv2, issues: List[ValidationIssue]) -> QualityScore:
        """Calculate quality scores based on IR and issues."""
        # Start with perfect scores
        clarity = 100.0
        specificity = 100.0
        completeness = 100.0
        consistency = 100.0

        # Deduct based on issues
        for issue in issues:
            impact = min(issue.score_impact, 30.0)  # Cap individual impact
            if issue.category == "clarity":
                clarity -= impact
            elif issue.category == "specificity":
                specificity -= impact
            elif issue.category == "completeness":
                completeness -= impact
            elif issue.category == "consistency":
                consistency -= impact

        # Floor at 0
        clarity = max(0.0, clarity)
        specificity = max(0.0, specificity)
        completeness = max(0.0, completeness)
        consistency = max(0.0, consistency)

        # Calculate total (weighted average)
        total = (
            clarity * 0.25 + specificity * 0.25 + completeness * 0.35 + consistency * 0.15
        )

        return QualityScore(
            total=total,
            clarity=clarity,
            specificity=specificity,
            completeness=completeness,
            consistency=consistency,
        )


def validate_prompt(ir: IRv2, original_text: Optional[str] = None) -> ValidationResult:
    """Convenience function to validate a prompt.

    Args:
        ir: Compiled IR v2
        original_text: Original prompt text (optional)

    Returns:
        ValidationResult with score and issues
    """
    validator = PromptValidator()
    return validator.validate(ir, original_text)


__all__ = [
    "ValidationIssue",
    "QualityScore",
    "ValidationResult",
    "PromptValidator",
    "validate_prompt",
]
