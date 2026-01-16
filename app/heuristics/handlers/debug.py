from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class LiveDebugHandler(BaseHandler):
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        # live debug marker from persona_evidence.flags
        flags = (md.get("persona_evidence") or {}).get("flags") or {}
        if flags.get("live_debug"):
            ir_v2.intents.append("debug")
