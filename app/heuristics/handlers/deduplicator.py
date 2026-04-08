from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class DeduplicatorHandler(BaseHandler):
    """Removes redundant constraints to save tokens and improve prompt quality."""

    # Bolt Optimization: Pre-calculate lowercase versions of redundant groups to prevent
    # redundant allocations and repeated `.lower()` calls inside nested loops.
    REDUNDANT_GROUPS_LOWER = [
        [
            "output strict json. do not output conversational text.",
            "no conversational filler. return only the requested format.",
        ],
        ["make it very short", "be brief"],
    ]

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        # Deduplicate ir_v1 constraints
        # Use a dynamic cache to prevent redundant string allocations while
        # safely respecting the in-place modifications of the constraints list.
        c1_lower_cache = {}
        for group in self.REDUNDANT_GROUPS_LOWER:
            found = []
            for c in ir_v1.constraints:
                if c not in c1_lower_cache:
                    c1_lower_cache[c] = c.lower()
                c_lower = c1_lower_cache[c]

                for item in group:
                    if item in c_lower or c_lower in item:
                        found.append(c)

            # Keep the first one, remove the rest
            if len(found) > 1:
                for f in found[1:]:
                    if f in ir_v1.constraints:
                        ir_v1.constraints.remove(f)

        # Deduplicate ir_v2 constraints
        c2_lower_cache = {}
        for group in self.REDUNDANT_GROUPS_LOWER:
            found = []
            for c in ir_v2.constraints:
                c_id = id(c)
                if c_id not in c2_lower_cache:
                    c2_lower_cache[c_id] = c.text.lower()
                c_lower = c2_lower_cache[c_id]

                for item in group:
                    if item in c_lower or c_lower in item:
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
