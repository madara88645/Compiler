"""Static analysis engine for prompts (The Linter).

Provides real-time feedback on prompt quality, safety, and best practices.
Optimized for performance (<50ms execution).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Set

# --- CONSTANTS & PATTERNS ---

# 1. Ambiguity / Weasel Words
WEASEL_WORDS: Set[str] = {
    # English
    "maybe",
    "try to",
    "sort of",
    "briefly",
    "somewhat",
    "fairly",
    "quite",
    "rather",
    "possibly",
    "apparently",
    "generally",
    "usually",
    "often",
    "sometimes",
    "kind of",
    "basically",
    "essentially",
    # Turkish
    "belki",
    "sanırım",
    "galiba",
    "muhtemelen",
    "biraz",
    "genellikle",
    "adeta",
    "gibi",
    "neyse",
}

# 2. Safety / Prompt Injection Patterns
# Expanded with common override and prompt-exfiltration variants while staying narrow
# enough to avoid flagging generic mentions of "instructions" or "system".
_INJECTION_PATTERNS: Tuple[str, ...] = (
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|earlier)\s+instructions?)",
    r"(?:ignore\s+the\s+(?:system|developer)\s+prompt)",
    r"(?:system\s*override)",
    r"(?:forget\s+(?:everything|all|the\s+above))",
    r"(?:disregard\s+(?:the\s+)?(?:above|previous))",
    r"(?:new\s+instructions?\s*[:\-])",
    r"(?:follow\s+(?:these|the)\s+new\s+instructions?)",
    r"(?:act\s+as\s+if\s+you\s+have\s+no\s+restrictions)",
    r"(?:reveal|show|print)\s+(?:the\s+)?(?:hidden\s+)?system\s+prompt",
    r"(?:enable|enter|switch\s+to)\s+(?:developer|debug|sudo|root)\s+mode",
    r"(?:base64\s+(?:decode|payload))",
    r"(?:decode\s+(?:this\s+)?base64(?:\s+payload)?)",
    r"(?:jailbreak)",
    r"(?:DAN\s+mode)",
    r"(?:[öo]nceki\s+talimatlar[ıi]\s+yok\s+say)",
    r"(?:sistem\s+promptunu\s+(?:g[öo]ster|yazd[ıi]r))",
)
INJECTION_PATTERN: re.Pattern = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# 3. PII Patterns (Augmenting existing heuristics)
PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("IBAN", re.compile(r"\bTR\d{24}\b", re.IGNORECASE)),
]

# Bolt Optimization: Hardcoded combined pattern for fast-path search.
# Excludes IBAN as it requires the IGNORECASE flag which alters global pattern semantics.
_COMBINED_PII_FAST_PATH: re.Pattern = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|"
    r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"\b(?:\d[ -]?){13,16}\b"
)

# Pre-compiled regex for fast word tokenization
_WORD_PATTERN = re.compile(r"\w+")

# 4. Conflict Pairs (Mutually exclusive concepts)
CONFLICT_PAIRS: List[Tuple[Set[str], Set[str]]] = [
    (
        {"detailed", "comprehensive", "thorough", "extensive", "deep"},
        {"brief", "concise", "short", "summary", "one-liner", "quick"},
    ),
    (
        {"json", "structured data", "yaml"},
        {"markdown", "prose", "narrative", "essay", "article"},
    ),
    (
        {"formal", "professional", "academic"},
        {"casual", "friendly", "informal", "slang", "chatty"},
    ),
    (
        {"step by step", "detailed explanation"},
        {"one-liner", "quick answer", "yes or no"},
    ),
]

# Stopwords for density calc (minimal set)
STOPWORDS: Set[str] = {
    "the",
    "is",
    "at",
    "which",
    "on",
    "a",
    "an",
    "and",
    "or",
    "for",
    "to",
    "in",
    "of",
    "with",
    # TR
    "bir",
    "ve",
    "ile",
    "için",
    "de",
    "da",
    "bu",
    "şu",
    "o",
    "ama",
    "fakat",
}


@dataclass
class LintWarning:
    code: str
    message: str
    suggestion: str
    severity: str  # "warning", "info"


@dataclass
class LintReport:
    score: int  # 0-100 overall health
    ambiguity_score: float  # 0-1 ratio (lower is better)
    density_score: float  # 0-1 ratio (higher is usually better, but not too high)
    warnings: List[LintWarning] = field(default_factory=list)
    safety_flags: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    masked_text: str = ""
    timing_ms: float = 0.0


class PromptLinter:
    """Static analysis engine for prompts."""

    def lint(self, text: str) -> LintReport:
        """Analyze prompt text and return a comprehensive report."""
        start_time = time.perf_counter()

        if not text or not text.strip():
            return LintReport(score=0, ambiguity_score=0.0, density_score=0.0, masked_text=text)

        # 1. Pre-processing
        lower_text = text.lower()
        words = _WORD_PATTERN.findall(lower_text)
        total_words = len(words)

        warnings: List[LintWarning] = []
        safety_flags: List[str] = []
        conflicts: List[str] = []

        # 2. Ambiguity Check
        # Bolt Optimization: map() with __contains__ is ~2.5x faster than an explicit loop
        weasel_count = sum(map(WEASEL_WORDS.__contains__, words))

        # Check for multi-word weasels (e.g. "try to") - simple heuristic check
        if "try to" in lower_text:
            weasel_count += 1
        if "kind of" in lower_text:
            weasel_count += 1
        if "sort of" in lower_text:
            weasel_count += 1

        ambiguity_score = weasel_count / total_words if total_words > 0 else 0.0

        if ambiguity_score > 0.05:
            warnings.append(
                LintWarning(
                    code="AMBIGUITY",
                    message=f"Prompt contains vague language ({int(ambiguity_score * 100)}% weasel words).",
                    suggestion="Replace words like 'maybe', 'try to' with imperative verbs.",
                    severity="warning",
                )
            )

        # 3. Density Check
        # Bolt Optimization: Set difference + loop is ~5x faster than set comprehension
        informative_words_count = 0
        for w in set(words) - STOPWORDS:
            if len(w) > 2:
                informative_words_count += 1
        density_score = informative_words_count / total_words if total_words > 0 else 0.0

        if density_score < 0.3 and total_words > 10:
            warnings.append(
                LintWarning(
                    code="LO_DENSITY",
                    message="Low information density.",
                    suggestion="Remove fluff words. Use a more 'telegraphic' style.",
                    severity="info",
                )
            )

        # 4. Safety Heuristics (Injection)
        if INJECTION_PATTERN.search(text):
            safety_flags.append("PROMPT_INJECTION_RISK")
            warnings.append(
                LintWarning(
                    code="INJECTION",
                    message="Potential prompt injection pattern detected.",
                    suggestion="Review for 'ignore instructions' or override commands.",
                    severity="warning",
                )
            )

        # 5. PII Masking
        masked_text = text
        has_common_pii = bool(_COMBINED_PII_FAST_PATH.search(text))
        for label, pattern in PII_PATTERNS:
            if label != "IBAN" and not has_common_pii:
                continue

            # Mask logic: detect, flag, and replace in masked_text
            # Bolt Optimization: subn avoids finding matches twice
            masked_text, count = pattern.subn(f"[{label}]", masked_text)
            if count > 0 and f"PII_{label}" not in safety_flags:
                safety_flags.append(f"PII_{label}")

        # 6. Conflict Detection
        for group_a, group_b in CONFLICT_PAIRS:
            # Bolt Optimization: explicit loops bypass generator overhead
            found_a = False
            for term in group_a:
                if term in lower_text:
                    found_a = True
                    break
            if not found_a:
                continue

            found_b = False
            for term in group_b:
                if term in lower_text:
                    found_b = True
                    break

            if found_a and found_b:
                desc_a = next(iter(group_a))
                desc_b = next(iter(group_b))
                conflicts.append(f"{desc_a} vs {desc_b}")
                warnings.append(
                    LintWarning(
                        code="CONFLICT",
                        message=f"Conflicting instructions detected ({desc_a} vs {desc_b}).",
                        suggestion="Choose one direction to avoid confusing the model.",
                        severity="warning",
                    )
                )

        # 7. Scoring
        # Start at 100, deduct for issues
        score = 100
        score -= int(ambiguity_score * 200)  # 0.05 ambiguity -> -10 pts
        if density_score < 0.3:
            score -= 10
        score -= len(safety_flags) * 30
        score -= len(conflicts) * 15

        score = max(0, min(100, score))

        end_time = time.perf_counter()
        timing_ms = (end_time - start_time) * 1000

        return LintReport(
            score=score,
            ambiguity_score=ambiguity_score,
            density_score=density_score,
            warnings=warnings,
            safety_flags=safety_flags,
            conflicts=conflicts,
            masked_text=masked_text,
            timing_ms=timing_ms,
        )
