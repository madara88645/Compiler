"""
Logic Analyzer - Offline Logic Extractor

This module provides advanced NLP-based logic extraction without requiring an LLM.
It detects negations, dependencies, missing information, and input/output mappings.
"""

from __future__ import annotations
import re
from typing import List, Optional
from dataclasses import dataclass, field


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class NegativeConstraint:
    """Represents a detected negative/restriction constraint."""

    original_text: str
    stripped_text: str  # Without the negation word
    negation_word: str
    anti_pattern: str  # Positive version (what TO do)


@dataclass
class DependencyRule:
    """Represents a detected causal/dependency relationship."""

    action: str
    reason: str
    full_text: str
    dependency_type: str  # "because", "so_that", "in_order_to", "if_then"


@dataclass
class MissingInfo:
    """Represents a detected reference to undefined/missing information."""

    entity: str
    context: str
    placeholder: str
    severity: str = "warning"


@dataclass
class IOMapping:
    """Represents detected input/output structure."""

    input_type: str
    process_action: str
    output_format: str
    confidence: float = 0.0


@dataclass
class LogicAnalysisResult:
    """Complete result from logic analysis."""

    negations: List[NegativeConstraint] = field(default_factory=list)
    dependencies: List[DependencyRule] = field(default_factory=list)
    missing_info: List[MissingInfo] = field(default_factory=list)
    io_mappings: List[IOMapping] = field(default_factory=list)


# ==============================================================================
# PATTERN DEFINITIONS
# ==============================================================================

# Negation patterns - ordered by specificity
NEGATION_PATTERNS = [
    # Strong negations
    (r"\b(never|absolutely\s+not|under\s+no\s+circumstances)\b", "strong"),
    (r"\b(do\s+not|don't|dont|doesn't|does\s+not)\b", "direct"),
    (r"\b(should\s+not|shouldn't|shouldnt|must\s+not|mustn't|mustnt)\b", "modal"),
    (r"\b(cannot|can't|can\s+not|can not)\b", "capability"),
    (r"\b(avoid|refrain\s+from|stay\s+away\s+from)\b", "avoidance"),
    (r"\b(exclude|omit|skip|bypass|ignore)\b", "exclusion"),
    (r"\b(without|except|unless)\b", "conditional"),
    (r"\b(no\s+\w+|none\s+of)\b", "absolute"),
    (r"\b(forbidden|prohibited|disallowed|banned)\b", "prohibition"),
]

# Causal/dependency patterns
DEPENDENCY_PATTERNS = [
    # Because patterns
    (r"(.+?)\s+because\s+(.+)", "because"),
    (r"(.+?)\s+since\s+(.+)", "because"),
    (r"(.+?)\s+as\s+(.+)", "because"),
    (r"(.+?)\s+due\s+to\s+(.+)", "because"),
    # So that patterns
    (r"(.+?)\s+so\s+that\s+(.+)", "so_that"),
    (r"(.+?)\s+in\s+order\s+to\s+(.+)", "in_order_to"),
    (r"(.+?)\s+to\s+ensure\s+(.+)", "in_order_to"),
    (r"(.+?)\s+for\s+the\s+purpose\s+of\s+(.+)", "in_order_to"),
    # If-then patterns
    (r"if\s+(.+?),?\s+then\s+(.+)", "if_then"),
    (r"when\s+(.+?),?\s+(.+)", "if_then"),
    (r"whenever\s+(.+?),?\s+(.+)", "if_then"),
    # Resulting patterns
    (r"(.+?)\s+(?:which|that)\s+will\s+(.+)", "result"),
    (r"(.+?)\s+so\s+(.+)", "result"),
]

# Missing information reference patterns
MISSING_REFERENCE_PATTERNS = [
    # Database/data references
    (
        r"\b(?:the|this|that|your|our|my)\s+(database|db|schema|table|data|dataset)\b",
        "Database Schema",
    ),
    (r"\b(?:the|this|that|your|our|my)\s+(api|endpoint|service|server)\b", "API Specification"),
    (
        r"\b(?:the|this|that|your|our|my)\s+(file|document|spreadsheet|csv|json|xml)\b",
        "File Content",
    ),
    (r"\b(?:the|this|that|your|our|my)\s+(code|script|function|class|module)\b", "Code Reference"),
    (
        r"\b(?:the|this|that|your|our|my)\s+(config|configuration|settings)\b",
        "Configuration Details",
    ),
    # Undefined entity references
    (r"\b(?:use|using|utilize|with)\s+(?:the|this|that)\s+(\w+)\b", "Entity Definition"),
    (r"\b(?:based\s+on|according\s+to)\s+(?:the|this|that)\s+(\w+)\b", "Reference Document"),
    # Pronoun ambiguity
    (r"\b(?:it|they|them|this|that|these|those)\s+(?:should|must|will|can)\b", "Pronoun Reference"),
]

# Input/Output detection patterns
INPUT_PATTERNS = [
    (
        r"\b(?:given|input|receive|accept|take|read)\s+(?:a|an|the)?\s*(\w+(?:\s+\w+)?)\b",
        "explicit",
    ),
    (r"\b(?:from|with)\s+(?:a|an|the)?\s*(\w+(?:\s+\w+)?)\s+(?:input|data|source)\b", "source"),
    (r"\b(?:text|code|number|json|xml|csv|image|audio|video)\b", "type"),
    (r"\b(?:user\s+input|prompt|query|request|message)\b", "user_input"),
]

OUTPUT_PATTERNS = [
    (
        r"\b(?:output|return|generate|produce|create|write)\s+(?:a|an|the)?\s*(\w+(?:\s+\w+)?)\b",
        "explicit",
    ),
    (r"\b(?:in|as)\s+(\w+)\s+format\b", "format"),
    (r"\b(?:save|export|send)\s+(?:to|as)\s+(\w+)\b", "destination"),
    (r"\b(?:markdown|json|xml|csv|html|pdf|text|table|list|code)\b", "format_type"),
]

PROCESS_PATTERNS = [
    (r"\b(?:analyze|parse|transform|convert|extract|filter|sort|group|aggregate)\b", "data_op"),
    (r"\b(?:compare|merge|split|join|combine)\b", "combine_op"),
    (r"\b(?:validate|check|verify|test|evaluate)\b", "validation"),
    (r"\b(?:summarize|explain|describe|document)\b", "text_op"),
    (r"\b(?:calculate|compute|measure|count)\b", "math_op"),
]


# ==============================================================================
# LOGIC ANALYZER CLASS
# ==============================================================================


class LogicAnalyzer:
    """
    Advanced logic extractor for prompt analysis.

    Detects:
    - Negative constraints and anti-patterns
    - Causal dependencies and reasoning chains
    - Missing/undefined information references
    - Input/output mappings
    """

    def __init__(self, maximize_recall: bool = True):
        """
        Initialize the LogicAnalyzer.

        Args:
            maximize_recall: If True, prefer false positives over missed detections.
        """
        self.maximize_recall = maximize_recall
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        self._negation_re = [(re.compile(p, re.IGNORECASE), t) for p, t in NEGATION_PATTERNS]
        self._dependency_re = [
            (re.compile(p, re.IGNORECASE | re.DOTALL), t) for p, t in DEPENDENCY_PATTERNS
        ]
        self._missing_re = [
            (re.compile(p, re.IGNORECASE), t) for p, t in MISSING_REFERENCE_PATTERNS
        ]
        self._input_re = [(re.compile(p, re.IGNORECASE), t) for p, t in INPUT_PATTERNS]
        self._output_re = [(re.compile(p, re.IGNORECASE), t) for p, t in OUTPUT_PATTERNS]
        self._process_re = [(re.compile(p, re.IGNORECASE), t) for p, t in PROCESS_PATTERNS]

    def analyze(self, text: str) -> LogicAnalysisResult:
        """
        Perform complete logic analysis on input text.

        Args:
            text: The prompt text to analyze.

        Returns:
            LogicAnalysisResult with all detected logic elements.
        """
        sentences = self._split_sentences(text)

        return LogicAnalysisResult(
            negations=self.detect_negations(text, sentences),
            dependencies=self.detect_dependencies(sentences),
            missing_info=self.detect_missing_info(text),
            io_mappings=self.detect_io_mapping(text),
        )

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences for analysis."""
        # Handle common sentence boundaries
        text = re.sub(r"([.!?])\s+", r"\1\n", text)
        # Handle bullet points and numbered lists
        text = re.sub(r"\n\s*[-*•]\s*", "\n", text)
        text = re.sub(r"\n\s*\d+[.):]\s*", "\n", text)

        sentences = [s.strip() for s in text.split("\n") if s.strip()]
        return sentences

    # --------------------------------------------------------------------------
    # NEGATION DETECTION
    # --------------------------------------------------------------------------

    def detect_negations(
        self, text: str, sentences: Optional[List[str]] = None
    ) -> List[NegativeConstraint]:
        """
        Detect negative constraints and extract anti-patterns.

        Identifies negation words and transforms them into:
        1. Negative Constraints (what NOT to do)
        2. Anti-Patterns (positive version - what TO do)
        """
        if sentences is None:
            sentences = self._split_sentences(text)

        negations = []
        seen = set()

        for sentence in sentences:
            for pattern, neg_type in self._negation_re:
                match = pattern.search(sentence)
                if match:
                    negation_word = match.group(1).lower()

                    # Skip if we've seen this exact sentence
                    if sentence in seen:
                        continue
                    seen.add(sentence)

                    # Strip negation to create anti-pattern
                    stripped = self._strip_negation(sentence, negation_word)
                    anti_pattern = self._create_anti_pattern(stripped, negation_word)

                    negations.append(
                        NegativeConstraint(
                            original_text=sentence,
                            stripped_text=stripped,
                            negation_word=negation_word,
                            anti_pattern=anti_pattern,
                        )
                    )
                    break  # Only capture first negation per sentence

        return negations

    def _strip_negation(self, sentence: str, negation_word: str) -> str:
        """Remove negation word from sentence."""
        # Create pattern that matches the negation word with surrounding context
        patterns = [
            rf"\b{re.escape(negation_word)}\s+",
            rf"\s+{re.escape(negation_word)}\b",
            rf"\b{re.escape(negation_word)}\b",
        ]
        result = sentence
        for p in patterns:
            result = re.sub(p, " ", result, flags=re.IGNORECASE)
        return " ".join(result.split())  # Normalize whitespace

    def _create_anti_pattern(self, stripped: str, negation_word: str) -> str:
        """Create a positive recommendation from a negative constraint."""
        # Map negation types to positive suggestions
        positive_prefix = {
            "never": "Always consider:",
            "do not": "Instead:",
            "don't": "Instead:",
            "avoid": "Prefer:",
            "refrain from": "Prefer:",
            "should not": "Should:",
            "shouldn't": "Should:",
            "must not": "Must:",
            "mustn't": "Must:",
            "cannot": "Can:",
            "can't": "Can:",
            "exclude": "Include:",
            "omit": "Include:",
            "skip": "Do not skip:",
            "without": "With:",
            "no": "Include:",
        }

        prefix = positive_prefix.get(negation_word.lower(), "Consider:")
        return f"{prefix} {stripped}"

    # --------------------------------------------------------------------------
    # DEPENDENCY DETECTION
    # --------------------------------------------------------------------------

    def detect_dependencies(self, sentences: List[str]) -> List[DependencyRule]:
        """
        Detect causal dependencies and reformat into Rule structures.

        Transforms:
        - "Do X because Y" -> Rule: [X] (Reason: [Y])
        - "Do X so that Y" -> Rule: [X] (Purpose: [Y])
        - "If X then Y" -> Rule: [Y] (Condition: [X])
        """
        dependencies = []
        seen = set()

        # Also check combined multi-sentence text for spanning dependencies
        full_text = " ".join(sentences)
        all_texts = sentences + [full_text]

        for text in all_texts:
            for pattern, dep_type in self._dependency_re:
                matches = pattern.finditer(text)
                for match in matches:
                    full_match = match.group(0).strip()

                    if full_match in seen or len(full_match) < 10:
                        continue
                    seen.add(full_match)

                    groups = match.groups()
                    if len(groups) >= 2:
                        part1, part2 = groups[0].strip(), groups[1].strip()

                        # Determine action vs reason based on dependency type
                        if dep_type == "if_then":
                            action, reason = part2, part1  # Then = action, If = condition
                        elif dep_type in ("because", "since"):
                            action, reason = part1, part2  # Action because Reason
                        else:
                            action, reason = part1, part2  # Action so that Purpose

                        if len(action) > 5 and len(reason) > 5:
                            dependencies.append(
                                DependencyRule(
                                    action=action,
                                    reason=reason,
                                    full_text=full_match,
                                    dependency_type=dep_type,
                                )
                            )

        return dependencies

    # --------------------------------------------------------------------------
    # MISSING INFORMATION DETECTION
    # --------------------------------------------------------------------------

    def detect_missing_info(self, text: str) -> List[MissingInfo]:
        """
        Detect references to undefined/missing information.

        Identifies:
        - "the database" without schema provided
        - "use the API" without endpoint details
        - Ambiguous pronoun references
        """
        missing = []
        seen = set()

        for pattern, info_type in self._missing_re:
            matches = pattern.finditer(text)
            for match in matches:
                entity = match.group(1) if match.lastindex else match.group(0)
                context = self._get_context(text, match.start(), match.end())

                key = f"{info_type}:{entity.lower()}"
                if key in seen:
                    continue
                seen.add(key)

                # Determine severity based on context
                severity = "warning"
                if any(word in entity.lower() for word in ["database", "api", "schema", "config"]):
                    severity = "error"

                missing.append(
                    MissingInfo(
                        entity=entity,
                        context=context,
                        placeholder=f"[MISSING: {info_type}]",
                        severity=severity,
                    )
                )

        # Maximize recall: also flag potential undefined references
        if self.maximize_recall:
            missing.extend(self._detect_potential_undefined(text, seen))

        return missing

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Extract surrounding context for a match."""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        context = text[ctx_start:ctx_end]
        if ctx_start > 0:
            context = "..." + context
        if ctx_end < len(text):
            context = context + "..."
        return context

    def _detect_potential_undefined(self, text: str, seen: set) -> List[MissingInfo]:
        """Additional heuristics for potential undefined references."""
        extras = []

        # Detect "the [noun]" patterns without prior definition
        pattern = re.compile(
            r"\b(?:the|this|that)\s+(\w+)\s+(?:is|should|will|must|can)\b", re.IGNORECASE
        )
        for match in pattern.finditer(text):
            entity = match.group(1)
            key = f"Entity:{entity.lower()}"
            if key not in seen and entity.lower() not in (
                "user",
                "system",
                "output",
                "input",
                "result",
                "response",
            ):
                seen.add(key)
                extras.append(
                    MissingInfo(
                        entity=entity,
                        context=self._get_context(text, match.start(), match.end()),
                        placeholder=f"[MISSING: {entity} definition]",
                        severity="info",
                    )
                )

        return extras

    # --------------------------------------------------------------------------
    # INPUT/OUTPUT MAPPING
    # --------------------------------------------------------------------------

    def detect_io_mapping(self, text: str) -> List[IOMapping]:
        """
        Detect input/output structure and create pseudo-algorithm blocks.

        Returns:
        Input: [Type] -> Process: [Action] -> Output: [Format]
        """
        inputs = self._detect_inputs(text)
        outputs = self._detect_outputs(text)
        processes = self._detect_processes(text)

        # Create mappings from detected elements
        mappings = []

        if inputs or outputs or processes:
            # Create primary mapping
            input_type = inputs[0] if inputs else "unspecified"
            output_format = outputs[0] if outputs else "unspecified"
            process_action = processes[0] if processes else "process"

            confidence = (
                (0.4 if inputs else 0.0) + (0.3 if outputs else 0.0) + (0.3 if processes else 0.0)
            )

            mappings.append(
                IOMapping(
                    input_type=input_type,
                    process_action=process_action,
                    output_format=output_format,
                    confidence=confidence,
                )
            )

            # Create secondary mappings if multiple elements detected
            for i in range(1, max(len(inputs), len(outputs), len(processes))):
                mappings.append(
                    IOMapping(
                        input_type=inputs[i] if i < len(inputs) else input_type,
                        process_action=processes[i] if i < len(processes) else process_action,
                        output_format=outputs[i] if i < len(outputs) else output_format,
                        confidence=confidence * 0.7,  # Lower confidence for secondary
                    )
                )

        return mappings

    def _detect_inputs(self, text: str) -> List[str]:
        """Detect input types from text."""
        inputs = []
        seen = set()
        for pattern, _ in self._input_re:
            for match in pattern.finditer(text):
                if match.lastindex:
                    value = match.group(1).strip().lower()
                else:
                    value = match.group(0).strip().lower()
                if value and value not in seen and len(value) < 30:
                    seen.add(value)
                    inputs.append(value)
        return inputs

    def _detect_outputs(self, text: str) -> List[str]:
        """Detect output formats from text."""
        outputs = []
        seen = set()
        for pattern, _ in self._output_re:
            for match in pattern.finditer(text):
                if match.lastindex:
                    value = match.group(1).strip().lower()
                else:
                    value = match.group(0).strip().lower()
                if value and value not in seen and len(value) < 30:
                    seen.add(value)
                    outputs.append(value)
        return outputs

    def _detect_processes(self, text: str) -> List[str]:
        """Detect processing actions from text."""
        processes = []
        seen = set()
        for pattern, _ in self._process_re:
            for match in pattern.finditer(text):
                value = match.group(0).strip().lower()
                if value and value not in seen:
                    seen.add(value)
                    processes.append(value)
        return processes

    # --------------------------------------------------------------------------
    # OUTPUT FORMATTING
    # --------------------------------------------------------------------------

    def format_restrictions_section(self, negations: List[NegativeConstraint]) -> str:
        """Format negations as a Restrictions section."""
        if not negations:
            return ""

        lines = ["### Restrictions", ""]
        for neg in negations:
            lines.append(f"- ❌ {neg.original_text}")
            lines.append(f"  - *Anti-pattern*: {neg.anti_pattern}")

        return "\n".join(lines)

    def format_dependency_rules(self, dependencies: List[DependencyRule]) -> str:
        """Format dependencies as structured rules."""
        if not dependencies:
            return ""

        lines = ["### Dependency Rules", ""]
        for dep in dependencies:
            reason_label = {
                "because": "Reason",
                "so_that": "Purpose",
                "in_order_to": "Goal",
                "if_then": "Condition",
                "result": "Result",
            }.get(dep.dependency_type, "Reason")

            lines.append(f"- **Rule**: {dep.action}")
            lines.append(f"  - *{reason_label}*: {dep.reason}")

        return "\n".join(lines)

    def format_missing_info_warnings(self, missing: List[MissingInfo]) -> str:
        """Format missing information as warnings."""
        if not missing:
            return ""

        lines = ["### Missing Information", ""]
        icons = {"error": "🔴", "warning": "🟡", "info": "🔵"}

        for item in missing:
            icon = icons.get(item.severity, "🔵")
            lines.append(f"- {icon} {item.placeholder}")
            lines.append(f"  - *Referenced*: `{item.entity}`")

        return "\n".join(lines)

    def format_io_algorithm(self, mappings: List[IOMapping]) -> str:
        """Format I/O mappings as pseudo-algorithm blocks."""
        if not mappings:
            return ""

        lines = ["### Input/Output Flow", "```"]
        for i, m in enumerate(mappings):
            conf = f" ({m.confidence:.0%} confidence)" if m.confidence < 1 else ""
            lines.append(f"[Flow {i+1}]{conf}")
            lines.append(f"  Input:   {m.input_type}")
            lines.append(f"  Process: {m.process_action}")
            lines.append(f"  Output:  {m.output_format}")
            if i < len(mappings) - 1:
                lines.append("")
        lines.append("```")

        return "\n".join(lines)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def analyze_prompt_logic(text: str, maximize_recall: bool = True) -> LogicAnalysisResult:
    """
    Convenience function to analyze prompt logic.

    Args:
        text: The prompt text to analyze.
        maximize_recall: Prefer catching potential issues over precision.

    Returns:
        LogicAnalysisResult with all detected elements.
    """
    analyzer = LogicAnalyzer(maximize_recall=maximize_recall)
    return analyzer.analyze(text)
