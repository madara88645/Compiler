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
                    category="safety",
                )
            elif flag == "financial":
                diag = DiagnosticItem(
                    severity="warning",
                    message="⚠️ Financial topic detected.",
                    suggestion="Do not provide investment advice. Treat as general financial information only.",
                    category="safety",
                )
            elif flag == "legal":
                diag = DiagnosticItem(
                    severity="warning",
                    message="⚠️ Legal topic detected.",
                    suggestion="Do not provide legal counsel. Recommend consulting a lawyer.",
                    category="safety",
                )
            elif flag == "security":
                diag = DiagnosticItem(
                    severity="info",
                    message="🛡️ Security topic detected.",
                    suggestion="Ensure ethical hacking guidelines are followed. Do not facilitate harm.",
                    category="safety",
                )

            if diag:
                ir_v2.diagnostics.append(diag)
                ir_v2.intents.append("risk")

        # Capability Mismatch Check
        original_text = md.get("original_text", "")
        if original_text:
            self.check_capability_mismatch(original_text, ir_v2)

    def check_capability_mismatch(self, text: str, ir_v2: IRv2) -> None:
        text_lower = text.lower()

        # Real-time keywords
        real_time_keywords = [
            "current time",
            "today's news",
            "weather",
            "stock price",
            "latest news",
        ]
        for kw in real_time_keywords:
            if kw in text_lower:
                ir_v2.diagnostics.append(
                    DiagnosticItem(
                        severity="warning",
                        message="⚠️ This model may not have real-time capabilities.",
                        suggestion="For real-time info like news or weather, verify with external tools or search.",
                        category="capability",
                    )
                )
                ir_v2.intents.append("capability_mismatch")
                break  # Avoid duplicate warnings for same category

        # Multi-modal keywords
        multi_modal_keywords = [
            "generate image",
            "create image",
            "draw",
            "create video",
            "generate video",
            "generate an image",
            "create an image",
            "generate a video",
            "create a video",
            "make an image",
            "make a video",
        ]
        for kw in multi_modal_keywords:
            if kw in text_lower:
                ir_v2.diagnostics.append(
                    DiagnosticItem(
                        severity="warning",
                        message="⚠️ This model is text-only.",
                        suggestion="This model cannot generate images or videos.",
                        category="capability",
                    )
                )
                ir_v2.intents.append("capability_mismatch")
                break
