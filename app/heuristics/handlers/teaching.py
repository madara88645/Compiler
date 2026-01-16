from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2

class TeachingHandler(BaseHandler):
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        if ir_v1.persona == "teacher":
            ir_v2.intents.append("teaching")
