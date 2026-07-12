from __future__ import annotations

import re

from app.heuristics import (
    detect_ambiguous_terms,
    detect_risk_flags,
    generate_clarify_questions,
)
from app.readiness.models import ReadinessReport, ReadinessSignal
from app.readiness.reference_rules import detect_unverifiable_references

GREETINGS = frozenset({"hi", "hello", "hey", "yo", "merhaba", "selam", "hola"})
# RISK_KEYWORDS categories that are genuinely sensitive. "infrastructure"
# (deploy/hosting) is intentionally excluded — it is context, not a blocker.
SENSITIVE_RISK = frozenset({"security", "privacy", "financial", "health", "legal"})
# Words that signal a vague ask even when no ambiguous term matches.
VAGUE_WORDS = frozenset(
    {"faster", "fast", "better", "good", "nicer", "nice", "cleaner", "improve", "optimize"}
)

# Auth/security patterns not covered by detect_risk_flags but clearly sensitive.
_AUTH_SECURITY_RE = re.compile(
    r"\b(password|authentication|authoriz\w*|session\s+auth|token\s+auth"
    r"|oauth|jwt|bcrypt|argon2|pbkdf2|scrypt)\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[A-Za-zğüşöçıİĞÜŞÖÇ]+")
_VOWEL_RE = re.compile(r"[aeıioöuüAEIİOÖUÜ]")
_SYMBOL_RUN_RE = re.compile(r"[^\w\s]{3,}")


def _is_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    words = _WORD_RE.findall(stripped)
    if not words:
        return True
    if len(stripped) <= 20 and all(w.lower() in GREETINGS for w in words):
        return True
    if _SYMBOL_RUN_RE.search(stripped) and len(words) <= 2:
        return True
    # Bolt Optimization: eliminate any() generator setup overhead
    if not _VOWEL_RE.search(stripped):
        return True
    return False


def _policy_review(ir: object | None) -> tuple[str | None, bool]:
    policy = getattr(ir, "policy", None)
    if policy is None:
        return None, False

    risk_level = str(getattr(policy, "risk_level", "") or "").strip().lower()
    execution_mode = str(getattr(policy, "execution_mode", "") or "").strip().lower()
    if risk_level != "high" and execution_mode != "human_approval_required":
        return None, False

    reasons: list[str] = []
    if risk_level == "high":
        reasons.append("high risk")
    if execution_mode == "human_approval_required":
        reasons.append("human approval required")
    return "Policy requires review: " + ", ".join(reasons) + ".", risk_level == "high"


def analyze_readiness(text: str, ir: object | None = None) -> ReadinessReport:
    if _is_noise(text):
        return ReadinessReport(
            verdict="noise",
            signals=[
                ReadinessSignal(
                    kind="noise",
                    message="This doesn't look like a real task — add a concrete request.",
                )
            ],
        )

    signals: list[ReadinessSignal] = []
    questions: list[str] = []

    risk_flags = [f for f in detect_risk_flags(text) if f in SENSITIVE_RISK]
    # Supplement with auth/security patterns not covered by the shared heuristic.
    if not risk_flags and _AUTH_SECURITY_RE.search(text):
        risk_flags = ["security"]
    for flag in risk_flags:
        signals.append(ReadinessSignal(kind="risk", message=f"Touches a sensitive area: {flag}."))

    policy_review_message, policy_is_high_risk = _policy_review(ir)

    references = detect_unverifiable_references(text)
    for ref in references:
        signals.append(
            ReadinessSignal(
                kind="unverifiable_reference",
                message=f"'{ref}' couldn't be verified — confirm it exists.",
            )
        )
        questions.append(f"Is '{ref}' a real, documented tool? Link its docs if so.")

    ambiguous_raw = detect_ambiguous_terms(text)
    # Reject terms that only appear as substrings of longer tokens (e.g. "fast" in "FastAPI").
    ambiguous = [
        t for t in ambiguous_raw if re.search(r"\b" + re.escape(t) + r"\b", text, re.IGNORECASE)
    ]
    lower_words = set(re.findall(r"\b\w+\b", text.lower()))
    is_vague = bool(ambiguous) or bool(lower_words & VAGUE_WORDS)
    if is_vague:
        signals.append(
            ReadinessSignal(
                kind="vagueness", message="The request is vague — specifics are missing."
            )
        )
        for question in generate_clarify_questions(ambiguous):
            if question not in questions:
                questions.append(question)

    questions = questions[:3]

    if risk_flags:
        verdict = "risky"
    elif references or is_vague:
        verdict = "clarify"
    else:
        verdict = "ready"

    if policy_review_message and (policy_is_high_risk or verdict == "ready"):
        signals.append(ReadinessSignal(kind="risk", message=policy_review_message))
        verdict = "risky"

    return ReadinessReport(verdict=verdict, signals=signals, questions=questions)
