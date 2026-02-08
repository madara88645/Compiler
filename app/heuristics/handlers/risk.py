from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, DiagnosticItem


class RiskHandler(BaseHandler):
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        flags = md.get("risk_flags", [])
        
        for flag in flags:
            diag = None
            if flag == "health":
                diag = DiagnosticItem(
                    severity="warning",
                    message="⚠️ Medical/Health topic detected.",
                    suggestion="Ensure content is for informational purposes only. Do not provide medical advice. Add a disclaimer.",
                    category="safety"
                )
            elif flag == "financial":
                diag = DiagnosticItem(
                    severity="warning",
                    message="⚠️ Financial topic detected.",
                    suggestion="Do not provide investment advice. Treat as general financial information only.",
                    category="safety"
                )
            elif flag == "legal":
                diag = DiagnosticItem(
                    severity="warning",
                    message="⚠️ Legal topic detected.",
                    suggestion="Do not provide legal counsel. Recommend consulting a lawyer.",
                    category="safety"
                )
            elif flag == "security":
                diag = DiagnosticItem(
                    severity="info",
                    message="🛡️ Security topic detected.",
                    suggestion="Ensure ethical hacking guidelines are followed. Do not facilitate harm.",
                    category="safety"
                )
            
            if diag:
                ir_v2.diagnostics.append(diag)
                ir_v2.intents.append("risk")
