"""
Safety Handler: Offline Guardrails and PII Detection

Provides deterministic safety checks without LLM calls:
- PII Detection (Email, Phone, Credit Cards)
- Unsafe Content Flags (Profanity, Injection keywords)
- Complexity/Length Guardrails
"""
import re
from typing import List, Dict, Any
from app.models import IR
from app.models_v2 import IRv2, DiagnosticItem


class SafetyHandler:
    """
    Scans prompt text for safety risks and injects diagnostics.
    """

    # -------------------------------------------------------------------------
    # REGEX PATTERNS
    # -------------------------------------------------------------------------

    # Generic PII patterns
    EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    PHONE_REGEX = re.compile(r"\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b")
    # Simple Luhn-like check isn't done here, just basic 13-19 digits
    CC_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

    # Unsafe keywords (Mock list for offline demo)
    # real system would use a more robust dictionary or Bloom filter
    UNSAFE_KEYWORDS = {
        "ignore previous instructions",
        "system prompt injection",
        "bypass",
        "jailbreak",
        "unfiltered",
        "hacking tool",
    }

    def handle(self, ir2: IRv2, ir1: IR) -> None:
        """
        Analyze text and populate ir2.diagnostics with safety warnings.
        """
        text = ir2.metadata.get("original_text", "")
        if not text:
            return

        diagnostics = []

        # 1. PII Detection
        pii_findings = self._scan_pii(text)
        for pii in pii_findings:
            diagnostics.append(
                DiagnosticItem(
                    severity="warning",
                    message=f"Possible PII detected: {pii['type']}",
                    suggestion="Anonymize personal data before sending to LLM.",
                    category="safety",
                )
            )

        # 2. Unsafe Content / Injection
        unsafe_flags = self._scan_unsafe_content(text)
        for flag in unsafe_flags:
            diagnostics.append(
                DiagnosticItem(
                    severity="critical",
                    message=f"Potential Safety Risk: '{flag}'",
                    suggestion="Remove adversarial patterns or unsafe content.",
                    category="security",
                )
            )

        # 3. Guardrails (Length/Complexity)
        length_warn = self._check_guardrails(text)
        if length_warn:
            diagnostics.append(length_warn)

        # Add to IR
        if diagnostics:
            ir2.diagnostics.extend(diagnostics)
            # Tag metadata
            ir2.metadata.setdefault("safety_flags", []).extend([d.message for d in diagnostics])

    def _scan_pii(self, text: str) -> List[Dict[str, str]]:
        findings = []

        if self.EMAIL_REGEX.search(text):
            findings.append({"type": "Email Address"})

        if self.PHONE_REGEX.search(text):
            findings.append({"type": "Phone Number"})

        if self.CC_REGEX.search(text):
            findings.append({"type": "Credit Card Number"})

        return findings

    def _scan_unsafe_content(self, text: str) -> List[str]:
        text_lower = text.lower()
        flags = []
        for kw in self.UNSAFE_KEYWORDS:
            if kw in text_lower:
                flags.append(kw)
        return flags

    def _check_guardrails(self, text: str) -> Any:
        length = len(text)

        if length < 10:
            return DiagnosticItem(
                severity="info",
                message="Prompt is extremely short",
                suggestion="Add more context for better results.",
                category="guardrail",
            )

        if length > 20000:
            return DiagnosticItem(
                severity="warning",
                message="Prompt is very long (>20k chars)",
                suggestion="Consider splitting or summarizing content.",
                category="performance",
            )

        return None
