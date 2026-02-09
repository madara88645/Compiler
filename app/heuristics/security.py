"""
Security Scanner Module.

Provides functions to detect and redact sensitive information (PII, Secrets)
from text before it is processed by LLMs.
"""

import re
from typing import List, Dict, NamedTuple


class Redaction(NamedTuple):
    original: str
    masked: str
    type: str
    start: int
    end: int


class SecurityResult(NamedTuple):
    is_safe: bool
    redacted_text: str
    findings: List[Dict[str, str]]


# Regex Patterns
PATTERNS = {
    # Secrets
    "openai_key": r"sk-[a-zA-Z0-9]{20,}",
    "github_token": r"ghp_[a-zA-Z0-9]{36}",
    "generic_api_key": r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{8,})['\"]?",
    "private_key": r"-----BEGIN RSA PRIVATE KEY-----",
    # PII
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    # Credit Card (Simple Luhn check not included, just pattern)
    # 4 groups of 4 digits, or 4-6-5 etc. simplifying to 13-19 digits
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
}

# Allow-list for common IP-like false positives
IP_ALLOWLIST = {"127.0.0.1", "0.0.0.0", "192.168.0.1", "192.168.1.1", "10.0.0.1"}


def scan_text(text: str) -> SecurityResult:
    """
    Scans text for sensitive information and returns a redacted version.
    """
    findings = []
    # redacted_text = text # Removed unused variable

    # We apply redactions in reverse order of matching to avoid index invalidation issues
    # But strings start replacing from left.
    # To do this robustly, we collect all matches, sort by start index, and rebuild string.

    matches = []

    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            val = match.group(0)

            # Special handling for generic key to capture just the value group if present
            if label == "generic_api_key" and match.lastindex and match.lastindex >= 2:
                # group(2) is the value
                val = match.group(2)
                span = match.span(2)
            else:
                span = match.span()

            # Filters
            if label == "ipv4" and val in IP_ALLOWLIST:
                continue
            if label == "credit_card":
                # Basic filter to avoid compilation versions like 3.12.10.15
                if "." in val or re.search(r"[a-fA-F]", val):  # Hex check just in case
                    continue
                # Length check for raw digits
                digits = re.sub(r"\D", "", val)
                if len(digits) < 13 or len(digits) > 19:
                    continue

            matches.append(
                {
                    "type": label,
                    "original": val,
                    "start": span[0],
                    "end": span[1],
                    "masked": f"[{label.upper()}_REDACTED]",
                }
            )

    # Deduplicate matches that overlap (prefer longer matches)
    # e.g. "sk-123" matched by key and something else
    # Simple strategy: sort by start pos. if overlap, skip shorter.
    matches.sort(key=lambda x: x["start"])

    final_matches = []
    last_end = -1

    for m in matches:
        if m["start"] >= last_end:
            final_matches.append(m)
            last_end = m["end"]
        else:
            # Overlap. Check if this one is strictly better (longer)?
            # For now, first come first served (sorted by start) usually works if patterns are distinct.
            # But "generic_key" might overlap "openai_key".
            # Let's trust specific patterns over generic ones?
            # Current implementation: regex iteration order matters.
            # Since we iterate dict, it's irrelevant.
            # Let's just keep the non-overlapping ones.
            pass

    # Rebuild text
    if not final_matches:
        return SecurityResult(is_safe=True, redacted_text=text, findings=[])

    result_parts = []
    current_idx = 0

    for m in final_matches:
        result_parts.append(text[current_idx : m["start"]])
        result_parts.append(m["masked"])
        current_idx = m["end"]

        findings.append(
            {
                "type": m["type"],
                "original": m["original"][:4] + "..." if len(m["original"]) > 8 else "***",
                "masked": m["masked"],
            }
        )

    result_parts.append(text[current_idx:])

    return SecurityResult(is_safe=False, redacted_text="".join(result_parts), findings=findings)
