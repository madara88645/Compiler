"""
Exploration Handler: adaptive exploration-mode scheduling.

Turns signals the compiler has already measured (problem cues in the user's
own words, diagnostic intents, ambiguity, complexity, risk/policy) into an
explicit per-step latitude budget: explore / decide / execute / verify.

Design rules:
- Silent for clear, trivial requests: every ``step.scheduling`` stays None and
  emitted text is byte-identical to a build without this handler. Only the
  ``uncertainty_profile`` metadata is written (always, for analytics).
- Deterministic: pure function of IR signals; reads no environment.
- Conservative: never invents steps — decide/verify are recorded in the
  profile and rendered as pseudo-steps, mirroring the [clarify]/[policy]
  precedent; ``ir.steps`` stays faithful to the user's words.

Runs LAST in the chain so it sees final intents and final policy.
"""

from __future__ import annotations

import re

from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, StepScheduling

# Problem stated in the user's own words. Mandatory for explore: diagnostic
# intents alone over-trigger (LIVE_DEBUG_KEYWORDS matches "log" inside
# "login"/"blog"), and bare asks ("fix a typo") are not diagnoses.
# Deliberately excluded: bare "error", "fails"/"failed" — they fire on
# "add error handling" and "find failed login attempts" style requests.
_PROBLEM_CUES = (
    "broken",
    "crash",
    "crashes",
    "crashing",
    "crashed",
    "bug",
    "traceback",
    "stack trace",
    "exception",
    "not working",
    "doesn't work",
    "does not work",
    "stopped working",
    "error message",
    "an error",
    "this error",
    "throws",
    "regression",
    "why is",
)
_DIAGNOSTIC_ASKS = (
    "fix",
    "debug",
    "diagnose",
    "troubleshoot",
    "investigate",
    "find out",
    "figure out",
    "resolve",
    "root cause",
    "help",
)

_MAX_SCORE = 7  # 2 (explore) + 1 (ambiguity) + 2 (complexity) + 1 (risk) + 1 (verify)


def _compile_patterns(markers: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(r"\b" + re.escape(marker) + r"\b") for marker in markers)


_CUE_PATTERNS = _compile_patterns(_PROBLEM_CUES)
_ASK_PATTERNS = _compile_patterns(_DIAGNOSTIC_ASKS)


def _first_match(
    patterns: tuple[re.Pattern[str], ...], markers: tuple[str, ...], text: str
) -> str | None:
    for pattern, marker in zip(patterns, markers):
        if pattern.search(text):
            return marker
    return None


class ExplorationHandler(BaseHandler):
    """Assign exploration modes to steps and write the uncertainty profile."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v2.metadata or {}
        text = str(md.get("original_text") or "").lower()
        intents = set(ir_v2.intents or [])
        ambiguous = md.get("ambiguous_terms") or []
        complexity = str(md.get("complexity") or "").lower()
        code_request = bool(md.get("code_request"))
        policy_reasons = md.get("policy_reasons") or []
        policy = ir_v2.policy

        signals: list[str] = []

        # R1 — explore: problem cue AND (diagnostic ask OR diagnostic intent).
        cue = _first_match(_CUE_PATTERNS, _PROBLEM_CUES, text)
        ask = _first_match(_ASK_PATTERNS, _DIAGNOSTIC_ASKS, text)
        diagnostic_intents = sorted({"troubleshooting", "debug"} & intents)
        explore = bool(cue and (ask or diagnostic_intents) and ir_v2.steps)
        if cue:
            signals.append(f"problem_cue:{cue}")
        if ask:
            signals.append(f"diagnostic_ask:{ask}")
        signals.extend(f"intent:{intent}" for intent in diagnostic_intents)

        # R2 — decide: convergence pseudo-step after a multi-step exploration.
        decide = explore and len(ir_v2.steps) >= 2

        # R3 — verify: destructive, or high-risk approval-gated concrete change.
        destructive = "destructive_operation" in policy_reasons
        concrete = code_request or "code" in intents
        high_risk_change = (
            not destructive
            and policy.risk_level == "high"
            and policy.execution_mode == "human_approval_required"
            and concrete
        )
        verify = destructive or high_risk_change

        # Informational score; modes are gated by the rules above, never by it.
        score = 0
        if explore:
            score += 2
        if ambiguous:
            score += 1
            signals.append(f"ambiguous_terms:{len(ambiguous)}")
        if complexity in ("medium", "high"):
            score += 1 if complexity == "medium" else 2
            signals.append(f"complexity:{complexity}")
        if policy.risk_level == "high":
            score += 1
            signals.append("risk:high")
        if verify:
            score += 1
            signals.append("destructive_operation" if destructive else "high_risk_change")

        level = "low" if score == 0 else "elevated" if score <= 2 else "high"
        confidence = round(score / _MAX_SCORE, 2)

        # R4 — execute backfill: only once another mode engaged; otherwise the
        # scheduler stays silent and every step keeps scheduling=None.
        if explore or verify:
            for index, step in enumerate(ir_v2.steps):
                if index == 0 and explore:
                    step.scheduling = StepScheduling(
                        mode="explore",
                        reason="diagnostic_request",
                        confidence=confidence,
                    )
                elif step.scheduling is None:
                    step.scheduling = StepScheduling(
                        mode="execute",
                        reason="scoped_execution",
                        confidence=confidence,
                    )

        verify_reason = None
        if destructive:
            verify_reason = "destructive_operation"
        elif high_risk_change:
            verify_reason = "high_risk_change"

        ir_v2.metadata["uncertainty_profile"] = {
            "level": level,
            "score": score,
            "signals": signals,
            "modes": {
                "explore": {
                    "scheduled": explore,
                    "reason": "diagnostic_request" if explore else None,
                },
                "decide": {
                    "scheduled": decide,
                    "reason": "convergence_after_exploration" if decide else None,
                },
                "verify": {"scheduled": verify, "reason": verify_reason},
            },
        }
