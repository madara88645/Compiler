from app.models_v2 import IRv2
from app.models import IR
from app.heuristics.logic_analyzer import analyze_prompt_logic

class LogicHandler:
    """
    Handler that integrates LogicAnalyzer results into IRv2 metadata.
    Detects negations, dependencies, and missing info.
    """
    
    def handle(self, ir2: IRv2, ir1: IR) -> None:
        """
        Run logic analysis on the original text and populate metadata.
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
                    "anti_pattern": n.anti_pattern
                } for n in analysis.negations
            ],
            "dependencies": [
                {
                    "action": d.action,
                    "reason": d.reason,
                    "type": d.dependency_type
                } for d in analysis.dependencies
            ],
            "missing_info": [
                {
                    "entity": m.entity,
                    "type": m.placeholder,
                    "severity": m.severity
                } for m in analysis.missing_info
            ],
            "io_flow": [
                {
                    "input": io.input_type,
                    "process": io.process_action,
                    "output": io.output_format,
                    "confidence": io.confidence
                } for io in analysis.io_mappings
            ]
        }

        # Enrich Diagnostics
        for missing in analysis.missing_info:
            severity = "warning" if missing.severity == "warning" else "error"
            ir2.diagnostics.append({
                "severity": severity,
                "message": f"Missing definition: {missing.entity}",
                "suggestion": f"Please clarify what '{missing.entity}' refers to.",
                "category": "logic"
            })

        # Enrich Constraints (exclude negations from standard list if handled by Logic?)
        # For now, let's explicit add Negative Constraints as 'restrictions'
        for neg in analysis.negations:
             ir2.constraints.append({
                 "text": neg.anti_pattern,
                 "origin": "heuristic:logic_negation",
                 "priority": 90,
                 "rationale": f"Derived from negative constraint: '{neg.original_text}'"
             })
