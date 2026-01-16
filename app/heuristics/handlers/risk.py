from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class RiskHandler(BaseHandler):
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        if md.get("risk_flags"):
            ir_v2.intents.append("risk")
