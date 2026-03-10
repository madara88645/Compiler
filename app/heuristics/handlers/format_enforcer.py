from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


class FormatEnforcerHandler(BaseHandler):
    """Injects strict constraints when data formats are requested."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        text = ir_v2.metadata.get("original_text", "")
        text_lower = text.lower()
        format_keywords = ["json", "csv", "xml", "table", "extract", "schema"]

        if any(kw in text_lower for kw in format_keywords):
            constraint_text = "No conversational filler. Return ONLY the requested format."

            # Update v1
            if constraint_text not in ir_v1.constraints:
                ir_v1.constraints.append(constraint_text)

            # Update v2
            if not any(c.text == constraint_text for c in ir_v2.constraints):
                ir_v2.constraints.append(ConstraintV2(type="formatting", text=constraint_text))
