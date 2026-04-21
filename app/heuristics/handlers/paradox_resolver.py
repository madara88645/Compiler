from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


def _contains_kw(text_lower: str, constraints_lower: str, kws: list[str]) -> bool:
    for k in kws:
        if k in text_lower or k in constraints_lower:
            return True
    return False


def _has_constraint(constraints: list[ConstraintV2], text: str) -> bool:
    for c in constraints:
        if c.text == text:
            return True
    return False


class ParadoxResolverHandler(BaseHandler):
    """Detects constraint paradoxes and injects resolution rules."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        text = ir_v2.metadata.get("original_text", "")
        text_lower = text.lower()
        constraints_lower = " ".join(ir_v1.constraints).lower()

        brief_kw = ["short", "brief", "concise"]
        detail_kw = ["detail", "comprehensive", "everything"]

        # Bolt Optimization: Replace any() generator expressions with fast-path loops to avoid overhead
        has_brief = _contains_kw(text_lower, constraints_lower, brief_kw)
        has_detail = _contains_kw(text_lower, constraints_lower, detail_kw)

        if has_brief and has_detail:
            resolution = "CONFLICT DETECTED: You have been asked to be both brief and detailed. Prioritize detail but use concise bullet points to remain brief."

            # Update v1
            if resolution not in ir_v1.constraints:
                ir_v1.constraints.append(resolution)

            # Update v2
            if not _has_constraint(ir_v2.constraints, resolution):
                ir_v2.constraints.append(ConstraintV2(type="resolution", text=resolution))
