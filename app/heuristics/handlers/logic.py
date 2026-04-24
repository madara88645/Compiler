from typing import List, Dict, Tuple
import re
from app.models_v2 import IRv2, ConstraintV2, DiagnosticItem
from app.models import IR
from app.heuristics.logic_analyzer import analyze_prompt_logic


_CONFLICT_DEFINITIONS = [
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

_COMPILED_CONFLICT_DEFINITIONS = [
    {"name": d["name"], "patterns": {k: re.compile(p) for k, p in d["patterns"].items()}}
    for d in _CONFLICT_DEFINITIONS
]

_COMPLEX_PATTERNS_RE = re.compile(
    r"(?i)\b(math|calculus|algebra|geometry|integral|derivative|equation|solve|algorithm|code|function|class|logic|reasoning|chain[- ]of[- ]thought|calculate|compute|matrix|analysis)\b"
)


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
        # Bolt Optimization: Pre-calculate constraints attributes to avoid repeated expensive getattr
        # calls inside nested loops.
        c_texts = [
            getattr(c, "text", "") if not isinstance(c, dict) else c.get("text", "") for c in ir2.constraints
        ]
        c_prios = [
            getattr(c, "priority", 40) if not isinstance(c, dict) else c.get("priority", 40)
            for c in ir2.constraints
        ]

        self._resolve_conflicts(ir2, c_texts, c_prios)

        # Re-fetch texts as they might have changed after conflict resolution
        c_texts = [
            getattr(c, "text", "") if not isinstance(c, dict) else c.get("text", "") for c in ir2.constraints
        ]
        self._inject_reasoning(ir2, original_text, c_texts)

    def _resolve_conflicts(self, ir2: IRv2, c_texts: List[str], c_prios: List[int]) -> None:
        """
        Identify and prune conflicting constraints based on priority.
        """
        # Iterate definitions
        for definition in _COMPILED_CONFLICT_DEFINITIONS:
            group_name = definition["name"]
            patterns = definition["patterns"]

            # Find matching constraints
            # Map: pattern_key -> list of (index, text, priority)
            matches: Dict[str, List[Tuple[int, str, int]]] = {k: [] for k in patterns}

            for i, text in enumerate(c_texts):
                # Ensure constraint is a ConstraintV2 object (handle dict if necessary, though IRv2 validator converts)
                # We'll assume object access if validator ran, but dict access if raw.

                for key, pattern in patterns.items():
                    if pattern.search(text):
                        matches[key].append((i, text, c_prios[i]))
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
                    for _, _, p in matches[key]:
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
                        for idx, t, p in matches[key]:
                            indices_to_remove.add(idx)
                            dropped_details.append(f"'{t}' (P:{p})")

                if indices_to_remove:
                    # Filter constraints
                    # Note: We must be careful if indices shift. Rebuilding list is safest.
                    new_constraints = [
                        c for i, c in enumerate(ir2.constraints) if i not in indices_to_remove
                    ]
                    ir2.constraints = new_constraints

                    # Also update our parallel lists for remaining definitions in this loop
                    c_texts[:] = [t for i, t in enumerate(c_texts) if i not in indices_to_remove]
                    c_prios[:] = [p for i, p in enumerate(c_prios) if i not in indices_to_remove]

                    # Add Diagnostic
                    msg = f"Conflict resolved in {group_name}: Kept {best_key} (P:{max_prio}), removed {', '.join(dropped_details)}."
                    ir2.diagnostics.append(
                        DiagnosticItem(severity="warning", message=msg, category="logic_conflict")
                    )

    def _inject_reasoning(self, ir2: IRv2, original_text: str, c_texts: List[str]) -> None:
        """
        Inject a <thinking> block constraint for complex reasoning tasks.
        """
        if _COMPLEX_PATTERNS_RE.search(original_text):
            # Check if thinking constraint already exists to avoid dupes
            # Iterate and check text
            for t in c_texts:
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
