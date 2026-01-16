import hashlib
from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2

class ConstraintHandler(BaseHandler):
    def _mk_id(self, text: str) -> str:
        return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:10]

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        origins = md.get("constraint_origins") or {}
        
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
        }
        
        c_v2: list[ConstraintV2] = []
        for c in ir_v1.constraints:
            origin = origins.get(c, "")
            pr = prio_map.get(origin, 40)
            c_v2.append(ConstraintV2(id=self._mk_id(c), text=c, origin=origin or "unknown", priority=pr))
        
        # Replace existing constraints in ir_v2 (assuming initialized empty or we overwrite)
        ir_v2.constraints = c_v2
