"""
Psycholinguist Handler.

Analyzes user sentiment, cognitive load, and cultural/language nuance
to adapt the system tone and provide actionable suggestions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


# -----------------------------------------------------------------------------
# Tone Matrix & Enums
# -----------------------------------------------------------------------------


class UserSentiment(Enum):
    NEUTRAL = "neutral"
    URGENT = "urgent"
    FRUSTRATED = "frustrated"
    CASUAL = "casual"


class FormalityLevel(Enum):
    FORMAL = "formal"  # Turkish: "Siz" form
    INFORMAL = "informal"  # Turkish: "Sen" form
    UNKNOWN = "unknown"


@dataclass
class ToneMatrix:
    """Maps user sentiment to recommended system persona adjustments."""

    sentiment: UserSentiment = UserSentiment.NEUTRAL
    recommended_tone: str = "Neutral, Helpful"
    persona_hint: str = ""

    # Predefined mappings
    MATRIX = {
        UserSentiment.NEUTRAL: ("Neutral, Helpful", ""),
        UserSentiment.URGENT: (
            "Brief, Direct, Solution-Oriented",
            "The user seems to be in a hurry. Prioritize actionable steps.",
        ),
        UserSentiment.FRUSTRATED: (
            "Empathetic, Apologetic, Calm",
            "The user appears frustrated. Acknowledge their issue first.",
        ),
        UserSentiment.CASUAL: (
            "Friendly, Conversational",
            "The user is casual. A lighter tone is appropriate.",
        ),
    }

    @classmethod
    def from_sentiment(cls, sentiment: UserSentiment) -> "ToneMatrix":
        tone, hint = cls.MATRIX.get(sentiment, cls.MATRIX[UserSentiment.NEUTRAL])
        return cls(sentiment=sentiment, recommended_tone=tone, persona_hint=hint)


@dataclass
class CognitiveLoadResult:
    """Result of cognitive load analysis."""

    idea_density: float = 0.0  # Propositions per sentence
    suggestion: Optional[str] = None
    is_high_load: bool = False
    is_low_load: bool = False


# -----------------------------------------------------------------------------
# Detection Logic
# -----------------------------------------------------------------------------

# Urgent keywords (case-insensitive)
URGENT_KEYWORDS = [
    "asap",
    "urgent",
    "now",
    "immediately",
    "broken",
    "critical",
    "emergency",
    "hurry",
    "acil",  # Turkish: urgent
    "hemen",  # Turkish: right now
    "şimdi",  # Turkish: now
]

# Frustration patterns
FRUSTRATION_PATTERNS = [
    r"[A-Z]{3,}",  # Multiple uppercase words (shouting)
    r"!{2,}",  # Multiple exclamation marks
    r"\?\!",  # ?! combo
    r"wtf|omg|ffs",  # Common frustration acronyms
    r"neden çalışmıyor",  # Turkish: why isn't it working
    r"yine mi",  # Turkish: again?
]

# Casual patterns
CASUAL_PATTERNS = [
    r"\bhey\b",
    r"\bhi\b",
    r"\byo\b",
    r"\bthanks\b",
    r"\bthx\b",
    r"\bselam\b",  # Turkish: hi
    r"\bnaber\b",  # Turkish: what's up
    r"\beyw\b",  # Turkish: thanks (slang)
]

# Turkish formality detection
TR_FORMAL_PATTERNS = [
    r"\bsiz\b",
    r"\bsizin\b",
    r"\bsizler\b",
    r"\blütfen\b",
    r"\befendim\b",
    r"\bsaygılarımla\b",
    r"\bmüsaade\b",
]

TR_INFORMAL_PATTERNS = [
    r"\bsen\b",
    r"\bsenin\b",
    r"\bya\b",
    r"\blan\b",
    r"\bkanka\b",
    r"\babi\b",
    r"\bhadi\b",
]


def detect_sentiment(text: str) -> UserSentiment:
    """Analyze text to detect user sentiment."""
    text_lower = text.lower()

    # Check for urgency
    for kw in URGENT_KEYWORDS:
        if kw in text_lower:
            return UserSentiment.URGENT

    # Check for frustration (patterns on original text for CAPS detection)
    for pattern in FRUSTRATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return UserSentiment.FRUSTRATED

    # Check for casual tone
    for pattern in CASUAL_PATTERNS:
        if re.search(pattern, text_lower):
            return UserSentiment.CASUAL

    return UserSentiment.NEUTRAL


def detect_formality(text: str) -> FormalityLevel:
    """Detect Turkish formality level (Siz vs Sen)."""
    text_lower = text.lower()

    formal_score = sum(1 for p in TR_FORMAL_PATTERNS if re.search(p, text_lower))
    informal_score = sum(1 for p in TR_INFORMAL_PATTERNS if re.search(p, text_lower))

    if formal_score > informal_score:
        return FormalityLevel.FORMAL
    elif informal_score > formal_score:
        return FormalityLevel.INFORMAL
    return FormalityLevel.UNKNOWN


def calculate_cognitive_load(text: str) -> CognitiveLoadResult:
    """
    Calculate cognitive load based on idea density.

    Idea Density = (Propositions / Sentences)
    A proposition is roughly estimated by counting verbs, nouns, and adjectives.
    """
    # Split into sentences
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    num_sentences = max(len(sentences), 1)

    # Rough proposition count: count words that look like content words
    # This is a simplistic heuristic; a real impl would use POS tagging.
    words = re.findall(r"\b\w{4,}\b", text)  # Words with 4+ chars as proxy
    num_propositions = len(words)

    idea_density = num_propositions / num_sentences

    result = CognitiveLoadResult(idea_density=idea_density)

    # Thresholds (tuned heuristically)
    if idea_density > 15:
        result.is_high_load = True
        result.suggestion = "Break this down into sub-tasks for clarity."
    elif idea_density < 3 and num_sentences > 2:
        result.is_low_load = True
        result.suggestion = "Consider summarizing to focus the request."

    return result


# -----------------------------------------------------------------------------
# Handler
# -----------------------------------------------------------------------------


class PsycholinguistHandler(BaseHandler):
    """
    Analyzes psycholinguistic signals in user prompts.

    Responsibilities:
    1. Detect user sentiment and adapt system tone.
    2. Analyze cognitive load and suggest breakdown/summarization.
    3. Detect TR/EN formality and enforce consistency.
    """

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        raw_text = (ir_v1.metadata or {}).get("original_text", "")

        # 1. Sentiment Detection & Tone Adaptation
        sentiment = detect_sentiment(raw_text)
        tone_matrix = ToneMatrix.from_sentiment(sentiment)

        ir_v2.metadata = ir_v2.metadata or {}
        ir_v2.metadata["user_sentiment"] = sentiment.value
        ir_v2.metadata["recommended_tone"] = tone_matrix.recommended_tone

        if tone_matrix.persona_hint:
            ir_v2.metadata["persona_hint"] = tone_matrix.persona_hint

        # 2. Cognitive Load Analysis
        cog_load = calculate_cognitive_load(raw_text)
        ir_v2.metadata["idea_density"] = round(cog_load.idea_density, 2)

        if cog_load.suggestion:
            ir_v2.metadata["cognitive_load_suggestion"] = cog_load.suggestion
            # Optionally add to intents
            if cog_load.is_high_load:
                ir_v2.intents.append("decompose")
            elif cog_load.is_low_load:
                ir_v2.intents.append("summarize")

        # 3. TR/EN Formality Detection
        formality = detect_formality(raw_text)
        if formality != FormalityLevel.UNKNOWN:
            ir_v2.metadata["formality_level"] = formality.value
            ir_v2.metadata["formality_enforcement"] = (
                "Use 'Siz' form in system prompt."
                if formality == FormalityLevel.FORMAL
                else "Use 'Sen' form in system prompt."
            )
