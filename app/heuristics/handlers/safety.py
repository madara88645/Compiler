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

    # Injection and exfiltration patterns (regex with word boundaries)
    # These patterns detect prompt injection and secret extraction attempts
    INJECTION_PATTERNS = [
        # Instruction override patterns - using flexible matching for multi-word phrases
        r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:any\s+)?(?:the\s+)?(?:your\s+)?(?:previous|above|prior|original|initial)(?:\s+(?:instructions?|prompts?|rules?|directions?|commands?))?",
        r"\b(?:ignore|disregard|forget|override)\s+(?:your|the)\s+(?:instructions?|prompts?|rules?|directions?|commands?)",
        r"\b(?:ignore|disregard|forget)\s+(?:everything|anything|what)\s+(?:you|was|were)\s+(?:told|said|instructed)",
        r"\bact\s+as\s+if\s+(?:you|your)\s+(?:previous|original|initial)\s+(?:instructions?|prompts?)",
        r"\breset\s+(?:your|the)\s+(?:instructions?|context|memory|system)",
        # Secret exfiltration patterns - flexible matching
        r"\b(?:reveal|show|print|display|output|tell|give|provide|share)\s+(?:me\s+)?(?:your|the|any|all)\s+(?:hidden\s+)?(?:secret\s+)?(?:original\s+)?(?:internal\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)",
        r"\b(?:reveal|show|print|display|output|tell|give|provide|share)\s+(?:me\s+)?(?:your|the|any|all)?\s*(?:api\s*keys?|secrets?|credentials?|passwords?|tokens?)",
        r"\b(?:what\s+(?:is|are)|list)\s+(?:your|the|any)\s+(?:api\s*keys?|secrets?|credentials?|passwords?)",
        r"\b(?:what\s+(?:is|are))\s+(?:your|the)\s+(?:hidden\s+)?(?:system\s+)?(?:prompt|instructions?)",
        # Jailbreak patterns
        r"\b(?:bypass|circumvent|break|escape|evade)\s+(?:your|the|any)?\s*(?:restrictions?|filters?|safety|guardrails?|rules?|limitations?)",
        r"\bjailbreak",
        r"\bunfiltered\s+(?:mode|response|output)",
        # Developer mode / DAN (Do Anything Now) patterns
        r"\b(?:developer|admin|debug|god)\s+mode",
        r"\bDAN\s+mode",
        r"\bact\s+as\s+if\s+you\s+(?:have\s+)?no\s+(?:restrictions?|rules?|limitations?)",
    ]

    # Compile patterns for faster matching
    # Bolt Optimization: Combine injection patterns into a single regex for 2x faster matching
    COMBINED_INJECTION_PATTERN = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

    def handle(self, ir2: IRv2, ir1: IR) -> None:
        """
        Analyze text and populate ir2.diagnostics with safety warnings.
        Also updates metadata.security and policy when threats are detected.
        """
        text = ir2.metadata.get("original_text", "")
        if not text:
            return

        diagnostics = []
        has_injection = False

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
            has_injection = True
            diagnostics.append(
                DiagnosticItem(
                    severity="critical",
                    message=f"Security threat detected: {flag}",
                    suggestion="This appears to be a prompt injection or secret exfiltration attempt.",
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

        # If injection detected, update security metadata and policy
        if has_injection:
            # Update security metadata to mark as unsafe
            # Use setdefault to ensure the key always exists (fixes #712 no-op bug)
            sec = ir2.metadata.setdefault(
                "security", {"is_safe": True, "findings": [], "redacted_text": text}
            )
            sec["is_safe"] = False
            sec["findings"].append(
                {
                    "type": "prompt_injection",
                    "message": "Prompt injection or secret exfiltration attempt detected",
                }
            )

            # Update policy to high risk
            ir2.policy.risk_level = "high"
            ir2.policy.data_sensitivity = "sensitive"
            ir2.policy.execution_mode = "advice_only"
            if "security" not in ir2.policy.risk_domains:
                ir2.policy.risk_domains.append("security")

            # Add to risk_flags in metadata so PolicyHandler can also see it
            ir1.metadata.setdefault("risk_flags", []).append("security_injection_attempt")

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
        """
        Scan text for prompt injection and secret exfiltration patterns.
        Returns list of matched pattern descriptions.
        """
        flags = []
        # Bolt Optimization: Fast-path boolean check using combined regex.
        # This preserves the original logic of flagging exactly one time per matched pattern
        # by falling back to the individual compiled patterns only if a match exists.
        if self.COMBINED_INJECTION_PATTERN.search(text):
            # Iterate through the original patterns to get the specific matches
            # compiling them dynamically here is fine since this is the slow path (rare)
            for raw_pattern in self.INJECTION_PATTERNS:
                match = re.search(raw_pattern, text, re.IGNORECASE)
                if match:
                    # Return the actual matched text (first 100 chars) for better diagnostics
                    matched_text = match.group(0)[:100]
                    flags.append(f"injection_pattern: {matched_text}")
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
