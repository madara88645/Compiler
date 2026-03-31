from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class DeduplicatorHandler(BaseHandler):
    """Removes redundant constraints to save tokens and improve prompt quality."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        # Define pairs/groups of redundant constraints
        redundant_groups = [
            [
                "Output strict JSON. Do not output conversational text.",
                "No conversational filler. Return ONLY the requested format.",
            ],
            ["Make it very short", "Be brief"],
        ]

        # Deduplicate ir_v1 constraints
        for group in redundant_groups:
            found = []
            for c in ir_v1.constraints:
                for item in group:
                    if item.lower() in c.lower() or c.lower() in item.lower():
                        found.append(c)

            # Keep the first one, remove the rest
            if len(found) > 1:
                for f in found[1:]:
                    if f in ir_v1.constraints:
                        ir_v1.constraints.remove(f)

        # Deduplicate ir_v2 constraints
        for group in redundant_groups:
            found = []
            for c in ir_v2.constraints:
                for item in group:
                    if item.lower() in c.text.lower() or c.text.lower() in item.lower():
                        found.append(c)

            # Keep the first one, remove the rest
            if len(found) > 1:
                for f in found[1:]:
                    if f in ir_v2.constraints:
                        ir_v2.constraints.remove(f)

        if ir_v2.intents:
            deduped_intents = []
            seen_intents = set()
            for intent in ir_v2.intents:
                normalized = intent.strip().lower()
                if not normalized or normalized in seen_intents:
                    continue
                seen_intents.add(normalized)
                deduped_intents.append(normalized)
            ir_v2.intents = deduped_intents
