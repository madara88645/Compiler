from typing import List, Dict, Tuple
import re
from app.models_v2 import IRv2, ConstraintV2, DiagnosticItem
from app.models import IR
from app.heuristics.logic_analyzer import analyze_prompt_logic


class LogicHandler:
    """
    Handler that integrates LogicAnalyzer results into IRv2 metadata.
    Detects negations, dependencies, missing info, and resolves conflicting constraints.
    """

    def handle(self, ir2: IRv2, ir1: IR) -> None:
        """
        Run logic analysis on the original text and populate metadata.
        Resolves conflicts and injects reasoning instructions.
        """
        # Analyze the raw text
        original_text = ir1.metadata.get("original_text", "")
        if not original_text:
            return

        analysis = analyze_prompt_logic(original_text)

        # Store structured results in metadata
        ir2.metadata["logic_analysis"] = {
            "negations": [
                {
                    "original": n.original_text,
                    "negation_word": n.negation_word,
                    "anti_pattern": n.anti_pattern,
                }
                for n in analysis.negations
            ],
            "dependencies": [
                {"action": d.action, "reason": d.reason, "type": d.dependency_type}
                for d in analysis.dependencies
            ],
            "missing_info": [
                {"entity": m.entity, "type": m.placeholder, "severity": m.severity}
                for m in analysis.missing_info
            ],
            "io_flow": [
                {
                    "input": io.input_type,
                    "process": io.process_action,
                    "output": io.output_format,
                    "confidence": io.confidence,
                }
                for io in analysis.io_mappings
            ],
        }

        # Enrich Diagnostics
        for missing in analysis.missing_info:
            severity = "warning" if missing.severity == "warning" else "error"
            ir2.diagnostics.append(
                DiagnosticItem(
                    severity=severity,
                    message=f"Missing definition: {missing.entity}",
                    suggestion=f"Please clarify what '{missing.entity}' refers to.",
                    category="logic",
                )
            )

        # Enrich Constraints with Negations
        for neg in analysis.negations:
            ir2.constraints.append(
                ConstraintV2(
                    text=neg.anti_pattern,
                    origin="heuristic:logic_negation",
                    priority=90,
                    rationale=f"Derived from negative constraint: '{neg.original_text}'",
                )
            )

        # New: Resolve conflicts and inject reasoning
        self._resolve_conflicts(ir2)
        self._inject_reasoning(ir2, original_text)

    def _resolve_conflicts(self, ir2: IRv2) -> None:
        """
        Identify and prune conflicting constraints based on priority.
        """
        # Define Pattern Groups
        # Each group contains mutually exclusive regex patterns
        # If constraints match different patterns within the same group, they conflict.
        conflict_definitions = [
            {
                "name": "Verbosity",
                "patterns": {
                    "concise": r"(?i)\b(concise|brief|short|succinct|compact)\b",
                    "detailed": r"(?i)\b(detail|comprehensive|thorough|extensive|step[- ]by[- ]step|explain)\b",
                },
            },
            {
                "name": "Output Format",
                "patterns": {
                    "json": r"(?i)\boutput\s+json\b",
                    "markdown": r"(?i)\boutput\s+markdown\b",
                    "csv": r"(?i)\boutput\s+csv\b",
                    "xml": r"(?i)\boutput\s+xml\b",
                    "yaml": r"(?i)\boutput\s+yaml\b",
                    "html": r"(?i)\boutput\s+html\b",
                },
            },
        ]

        # Iterate definitions
        for definition in conflict_definitions:
            group_name = definition["name"]
            patterns = definition["patterns"]

            # Find matching constraints
            # Map: pattern_key -> list of (index, ConstraintV2)
            matches: Dict[str, List[Tuple[int, ConstraintV2]]] = {k: [] for k in patterns}

            for i, constraint in enumerate(ir2.constraints):
                # Ensure constraint is a ConstraintV2 object (handle dict if necessary, though IRv2 validator converts)
                # We'll assume object access if validator ran, but dict access if raw.
                # Safe access:
                text = getattr(
                    constraint,
                    "text",
                    constraint.get("text", "") if isinstance(constraint, dict) else "",
                )

                for key, pattern in patterns.items():
                    if re.search(pattern, text):
                        matches[key].append((i, constraint))
                        # Assume one pattern match per constraint is sufficient for bucketing
                        break

            # Check for conflict: matches found in > 1 unique key buckets
            active_keys = [k for k, v in matches.items() if v]
            if len(active_keys) > 1:
                # Conflict detected!

                # Determine winner key: highest max priority among its constraints
                best_key = None
                max_prio = -1

                for key in active_keys:
                    # Get max priority for this bucket
                    key_max = -1
                    for _, constr in matches[key]:
                        p = getattr(
                            constr,
                            "priority",
                            constr.get("priority", 40) if isinstance(constr, dict) else 40,
                        )
                        if p > key_max:
                            key_max = p

                    if key_max > max_prio:
                        max_prio = key_max
                        best_key = key
                    elif key_max == max_prio:
                        # Tie-breaker: prefer first encountered bucket (arbitrary)
                        if best_key is None:
                            best_key = key

                # Remove constraints from all other keys
                indices_to_remove = set()
                dropped_details = []

                for key in active_keys:
                    if key != best_key:
                        for idx, constr in matches[key]:
                            indices_to_remove.add(idx)
                            t = getattr(
                                constr,
                                "text",
                                constr.get("text", "") if isinstance(constr, dict) else "",
                            )
                            p = getattr(
                                constr,
                                "priority",
                                constr.get("priority", 0) if isinstance(constr, dict) else 0,
                            )
                            dropped_details.append(f"'{t}' (P:{p})")

                if indices_to_remove:
                    # Filter constraints
                    # Note: We must be careful if indices shift. Rebuilding list is safest.
                    new_constraints = [
                        c for i, c in enumerate(ir2.constraints) if i not in indices_to_remove
                    ]
                    ir2.constraints = new_constraints

                    # Add Diagnostic
                    msg = f"Conflict resolved in {group_name}: Kept {best_key} (P:{max_prio}), removed {', '.join(dropped_details)}."
                    ir2.diagnostics.append(
                        DiagnosticItem(severity="warning", message=msg, category="logic_conflict")
                    )

    def _inject_reasoning(self, ir2: IRv2, original_text: str) -> None:
        """
        Inject a <thinking> block constraint for complex reasoning tasks.
        """
        complex_patterns = r"(?i)\b(math|calculus|algebra|geometry|integral|derivative|equation|solve|algorithm|code|function|class|logic|reasoning|chain[- ]of[- ]thought|calculate|compute|matrix|analysis)\b"

        if re.search(complex_patterns, original_text):
            # Check if thinking constraint already exists to avoid dupes
            # Iterate and check text
            for c in ir2.constraints:
                t = getattr(c, "text", c.get("text", "") if isinstance(c, dict) else "")
                if "<thinking>" in t:
                    return

            ir2.constraints.append(
                ConstraintV2(
                    text="Enclose your internal reasoning and step-by-step analysis in <thinking>...</thinking> tags before the final answer.",
                    origin="heuristic:logic_reasoning",
                    priority=95,  # High priority
                    rationale="Complex task detected requiring Chain-of-Thought.",
                )
            )
            # Log info
            ir2.diagnostics.append(
                DiagnosticItem(
                    severity="info",
                    message="Injected <thinking> block requirement for complex task.",
                    category="logic_reasoning",
                )
            )
