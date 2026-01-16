from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class ContentHandler(BaseHandler):
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}

        if md.get("summary") == "true":
            ir_v2.intents.append("summary")

        if md.get("comparison_items"):
            ir_v2.intents.append("compare")

        if md.get("variant_count", 1) > 1:
            ir_v2.intents.append("variants")

        if md.get("code_request"):
            ir_v2.intents.append("code")

        if md.get("ambiguous_terms"):
            ir_v2.intents.append("ambiguous")

        if "web" in (ir_v1.tools or []):
            ir_v2.intents.append("recency")
