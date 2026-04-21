from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


def _contains_any(text_lower: str, kws: list[str]) -> bool:
    for k in kws:
        if k in text_lower:
            return True
    return False


def _has_constraint(constraints: list[ConstraintV2], text: str) -> bool:
    for c in constraints:
        if c.text == text:
            return True
    return False


class FormatEnforcerHandler(BaseHandler):
    """Injects strict constraints when data formats are requested."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        text = ir_v2.metadata.get("original_text", "")
        text_lower = text.lower()
        format_keywords = ["json", "csv", "xml", "table", "extract", "schema"]

        # Bolt Optimization: Replace any() generator expressions with fast-path loops to avoid overhead
        if _contains_any(text_lower, format_keywords):
            constraint_text = "No conversational filler. Return ONLY the requested format."

            # Update v1
            if constraint_text not in ir_v1.constraints:
                ir_v1.constraints.append(constraint_text)

            # Update v2
            if not _has_constraint(ir_v2.constraints, constraint_text):
                ir_v2.constraints.append(ConstraintV2(type="formatting", text=constraint_text))
