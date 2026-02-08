"""
Enhanced Constraint Handler with Logic Analysis

Integrates the LogicAnalyzer for advanced constraint extraction:
- Negative constraint detection (detect_negations)
- Dependency mapping (detect_dependencies)
- Missing information warnings
- Input/Output flow analysis
"""
import hashlib
from typing import List
from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2, DiagnosticItem
from app.heuristics.logic_analyzer import LogicAnalyzer, LogicAnalysisResult


class ConstraintHandler(BaseHandler):
    """
    Enhanced constraint handler with logic analysis capabilities.

    Extends basic constraint handling with:
    - Negation detection and anti-pattern extraction
    - Dependency/causality detection
    - Missing information detection
    - Input/Output mapping
    """

    def __init__(self, maximize_recall: bool = True):
        """
        Initialize the handler with a LogicAnalyzer.

        Args:
            maximize_recall: If True, prefer catching potential issues over precision.
        """
        self._logic_analyzer = LogicAnalyzer(maximize_recall=maximize_recall)

    def _mk_id(self, text: str) -> str:
        """Generate a short hash ID for a constraint."""
        return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:10]

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        """
        Process constraints from IR v1 and enhance with logic analysis.

        This method:
        1. Converts basic IR v1 constraints to v2 format
        2. Runs logic analysis on the original prompt
        3. Adds extracted negative constraints
        4. Adds dependency rules as constraints
        5. Adds missing info and I/O diagnostics
        """
        md = ir_v1.metadata or {}
        origins = md.get("constraint_origins") or {}
        original_text = md.get("original_text", "")

        prio_map = {
            "recency": 80,
            "risk_flags": 70,
            "live_debug": 80,
            "pii": 60,
            "teaching_duration": 65,
            "teaching_level": 60,
            "teaching": 60,
            "comparison": 50,
            "variants": 50,
            "summary": 40,
            "summary_limit": 40,
            "ambiguous_terms": 30,
            "code_request": 30,
            # New logic analysis origins
            "negation": 85,
            "restriction": 85,
            "dependency": 75,
            "io_flow": 50,
        }

        # Step 1: Convert existing IR v1 constraints
        c_v2: List[ConstraintV2] = []
        for c in ir_v1.constraints:
            origin = origins.get(c, "")
            pr = prio_map.get(origin, 40)
            c_v2.append(
                ConstraintV2(id=self._mk_id(c), text=c, origin=origin or "unknown", priority=pr)
            )

        # Step 2: Run logic analysis if we have original text
        if original_text:
            analysis = self._logic_analyzer.analyze(original_text)

            # Add negation constraints
            neg_constraints = self.detect_negations(analysis)
            c_v2.extend(neg_constraints)

            # Add dependency constraints
            dep_constraints = self.detect_dependencies(analysis)
            c_v2.extend(dep_constraints)

            # Add I/O flow constraints
            io_constraints = self._extract_io_constraints(analysis)
            c_v2.extend(io_constraints)

            # Add diagnostics for missing info
            diagnostics = self._extract_diagnostics(analysis)
            ir_v2.diagnostics.extend(diagnostics)

            # Store analysis metadata
            ir_v2.metadata["logic_analysis"] = {
                "negation_count": len(analysis.negations),
                "dependency_count": len(analysis.dependencies),
                "missing_info_count": len(analysis.missing_info),
                "io_mapping_count": len(analysis.io_mappings),
            }

        # Deduplicate constraints by ID
        seen_ids = set()
        unique_constraints = []
        for c in c_v2:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                unique_constraints.append(c)

        ir_v2.constraints = unique_constraints

    # --------------------------------------------------------------------------
    # NEGATION DETECTION
    # --------------------------------------------------------------------------

    def detect_negations(self, analysis: LogicAnalysisResult) -> List[ConstraintV2]:
        """
        Extract negative constraints from logic analysis.

        Creates constraints in the format:
        - ❌ RESTRICTION: [original negative statement]

        Also creates anti-pattern hints in the rationale.
        """
        constraints = []

        for neg in analysis.negations:
            # Create the restriction constraint
            constraint_text = f"❌ RESTRICTION: {neg.original_text}"

            constraints.append(
                ConstraintV2(
                    id=self._mk_id(neg.original_text),
                    text=constraint_text,
                    origin="restriction",
                    priority=85,
                    rationale=f"Anti-pattern: {neg.anti_pattern}",
                )
            )

        return constraints

    # --------------------------------------------------------------------------
    # DEPENDENCY DETECTION
    # --------------------------------------------------------------------------

    def detect_dependencies(self, analysis: LogicAnalysisResult) -> List[ConstraintV2]:
        """
        Extract dependency rules from logic analysis.

        Creates constraints in the format:
        - Rule: [Action] (Reason: [Justification])
        """
        constraints = []

        reason_labels = {
            "because": "Reason",
            "so_that": "Purpose",
            "in_order_to": "Goal",
            "if_then": "Condition",
            "result": "Result",
        }

        for dep in analysis.dependencies:
            label = reason_labels.get(dep.dependency_type, "Reason")
            constraint_text = f"📋 RULE: {dep.action}"
            rationale = f"{label}: {dep.reason}"

            constraints.append(
                ConstraintV2(
                    id=self._mk_id(dep.full_text),
                    text=constraint_text,
                    origin="dependency",
                    priority=75,
                    rationale=rationale,
                )
            )

        return constraints

    # --------------------------------------------------------------------------
    # I/O FLOW EXTRACTION
    # --------------------------------------------------------------------------

    def _extract_io_constraints(self, analysis: LogicAnalysisResult) -> List[ConstraintV2]:
        """
        Extract input/output flow constraints from logic analysis.

        Creates constraints describing the expected data flow.
        """
        constraints = []

        for i, io in enumerate(analysis.io_mappings):
            if io.confidence < 0.3:
                continue  # Skip low-confidence mappings

            flow_text = f"🔄 FLOW: Input({io.input_type}) → Process({io.process_action}) → Output({io.output_format})"

            constraints.append(
                ConstraintV2(
                    id=self._mk_id(f"io_flow_{i}_{io.input_type}"),
                    text=flow_text,
                    origin="io_flow",
                    priority=50,
                    rationale=f"Confidence: {io.confidence:.0%}",
                )
            )

        return constraints

    # --------------------------------------------------------------------------
    # DIAGNOSTIC EXTRACTION
    # --------------------------------------------------------------------------

    def _extract_diagnostics(self, analysis: LogicAnalysisResult) -> List[DiagnosticItem]:
        """
        Convert missing information to diagnostics.

        Creates warnings/errors for:
        - Undefined entity references
        - Missing schemas/configs
        - Ambiguous pronoun references
        """
        diagnostics = []

        severity_map = {
            "error": "error",
            "warning": "warning",
            "info": "info",
        }

        for missing in analysis.missing_info:
            diagnostics.append(
                DiagnosticItem(
                    severity=severity_map.get(missing.severity, "warning"),
                    message=f"Missing: {missing.entity}",
                    suggestion=f"Please provide {missing.placeholder.replace('[MISSING: ', '').replace(']', '')}",
                    category="missing_info",
                )
            )

        # Add summary diagnostic if there are many issues
        if len(analysis.missing_info) > 3:
            diagnostics.append(
                DiagnosticItem(
                    severity="warning",
                    message=f"Multiple undefined references detected ({len(analysis.missing_info)} total)",
                    suggestion="Consider providing more context or definitions for referenced entities.",
                    category="completeness",
                )
            )

        return diagnostics

    # --------------------------------------------------------------------------
    # UTILITY METHODS
    # --------------------------------------------------------------------------

    def analyze_text(self, text: str) -> LogicAnalysisResult:
        """
        Directly analyze text without going through IR.

        Useful for standalone analysis or testing.
        """
        return self._logic_analyzer.analyze(text)

    def get_restrictions_markdown(self, text: str) -> str:
        """Generate a Restrictions section in Markdown from text."""
        analysis = self._logic_analyzer.analyze(text)
        return self._logic_analyzer.format_restrictions_section(analysis.negations)

    def get_dependency_rules_markdown(self, text: str) -> str:
        """Generate a Dependency Rules section in Markdown from text."""
        analysis = self._logic_analyzer.analyze(text)
        return self._logic_analyzer.format_dependency_rules(analysis.dependencies)

    def get_missing_info_markdown(self, text: str) -> str:
        """Generate a Missing Information section in Markdown from text."""
        analysis = self._logic_analyzer.analyze(text)
        return self._logic_analyzer.format_missing_info_warnings(analysis.missing_info)

    def get_io_flow_markdown(self, text: str) -> str:
        """Generate an I/O Flow section in Markdown from text."""
        analysis = self._logic_analyzer.analyze(text)
        return self._logic_analyzer.format_io_algorithm(analysis.io_mappings)
