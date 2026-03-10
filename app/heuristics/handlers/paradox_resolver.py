from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


class ParadoxResolverHandler(BaseHandler):
    """Detects constraint paradoxes and injects resolution rules."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        text = ir_v2.metadata.get("original_text", "")
        text_lower = text.lower()
        constraints_lower = " ".join(ir_v1.constraints).lower()

        brief_kw = ["short", "brief", "concise"]
        detail_kw = ["detail", "comprehensive", "everything"]

        has_brief = any(k in text_lower or k in constraints_lower for k in brief_kw)
        has_detail = any(k in text_lower or k in constraints_lower for k in detail_kw)

        if has_brief and has_detail:
            resolution = "CONFLICT DETECTED: You have been asked to be both brief and detailed. Prioritize detail but use concise bullet points to remain brief."

            # Update v1
            if resolution not in ir_v1.constraints:
                ir_v1.constraints.append(resolution)

            # Update v2
            if not any(c.text == resolution for c in ir_v2.constraints):
                ir_v2.constraints.append(ConstraintV2(type="resolution", text=resolution))
