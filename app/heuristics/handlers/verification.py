"""
Verification Handler: constraint-grounded self-check checklist.

Emits a short "before you finish, verify" block built ONLY from constraints the
compiler already extracted from the user's own words. This is the self-
verification prompting pattern (ask the model to check its work against explicit
criteria before finalising), grounded so that it cannot invent a requirement.

Why it earns its place, given `Key Constraints` already exists:

- `emit_system_prompt_v2` renders `_top_constraints_text_v2(..., limit=3)`, so
  only the three highest-priority constraints ever reach the system prompt. A
  request like "must not expose user emails and should never log request
  bodies; exclude soft-deleted rows; do not add new dependencies" produces a
  dozen constraints, and the email requirement is silently dropped. The
  checklist covers every hard requirement, so nothing the user said is lost.
- A stated constraint and an instruction to verify against it do different
  things. The former is context; the latter is a final pass.

Design rules (mirroring exploration.py):
- Deterministic: a pure function of constraints already on the IR. No LLM, no
  network, no clock, no randomness.
- Conservative: every line is a restatement of an existing constraint. The
  handler never adds a requirement, metric, or API name of its own.
- Silent unless it pays for itself: needs at least MIN_ITEMS distinct hard
  requirements, otherwise `Key Constraints` already says everything and the
  block would be ceremony.
- Lossless de-duplication: the compiler records the same restriction twice (a
  scoped clause from the logic analyser plus the user's full sentence). Items
  contained within a more complete item are collapsed into it, so the longest
  faithful phrasing survives.
"""

from __future__ import annotations

import re

from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2

# Constraint origins that represent a checkable requirement stated by the user.
# Everything else is either a clarification request, a description of the data
# flow, or a rendering directive already handled elsewhere.
_CHECKABLE_ORIGINS = frozenset(
    {
        "heuristic:logic_negation",
        "restriction",
        "structure_handler",
    }
)

# Constraints below this priority are advisory rather than hard requirements.
_MIN_PRIORITY = 70

# Below this many distinct requirements, `Key Constraints` already covers them.
MIN_ITEMS = 2

# Never list more than this — a checklist the model skims is worse than none.
MAX_ITEMS = 7

# Decoration the emitters add for display; irrelevant when comparing meaning.
_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:[^\w\s]+\s*)?"
    r"(?:restriction|flow|note|rule)\s*:\s*",
    re.IGNORECASE,
)

# The imperative prefix the logic analyser attaches ("Must not: ", "Never: ").
# Stripped for comparison only, so a scoped clause can be recognised inside the
# user's original sentence. The displayed text keeps its prefix.
_IMPERATIVE_PREFIX_RE = re.compile(
    r"^\s*(?:must not|should not|does not|do not|under no circumstances|"
    r"refrain from|stay away from|never|avoid|exclude|omit|skip|bypass|ignore|"
    r"without|except|unless|none of|forbidden|prohibited|disallowed|banned|no)"
    r"\s*:\s*",
    re.IGNORECASE,
)

_NON_WORD_RE = re.compile(r"[^a-z0-9]+")

_HEADINGS = {
    "en": "Before you finish, verify each of these against your answer:",
    "tr": "Bitirmeden once yanitini asagidakilerin her biriyle karsilastir:",
    "es": "Antes de terminar, verifica tu respuesta con cada uno de estos puntos:",
}


def _comparable(text: str) -> str:
    """Reduce a constraint to a bag of words for containment comparison."""
    stripped = _LABEL_PREFIX_RE.sub("", text or "")
    stripped = _IMPERATIVE_PREFIX_RE.sub("", stripped)
    return _NON_WORD_RE.sub(" ", stripped.lower()).strip()


def _display(text: str) -> str:
    """Strip display decoration so checklist lines read uniformly."""
    return _LABEL_PREFIX_RE.sub("", text or "").strip()


class VerificationHandler(BaseHandler):
    """Builds ``ir_v2.metadata['verification_checklist']`` from hard constraints."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        checklist = self.build_checklist(ir_v2)
        if checklist:
            ir_v2.metadata["verification_checklist"] = checklist

    def build_checklist(self, ir_v2: IRv2) -> list[str]:
        candidates: list[tuple[str, str]] = []  # (display, comparable)
        for constraint in ir_v2.constraints:
            origin = getattr(constraint, "origin", "") or ""
            priority = getattr(constraint, "priority", 0) or 0
            text = getattr(constraint, "text", "") or ""
            if origin not in _CHECKABLE_ORIGINS or priority < _MIN_PRIORITY:
                continue
            # The JSON Schema constraint is a whole code block; it is already
            # surfaced as "[JSON Schema Enforced]" and would swamp the list.
            if getattr(constraint, "id", "") == "schema_enforcement" or "```" in text:
                continue
            comparable = _comparable(text)
            if not comparable:
                continue
            candidates.append((_display(text), comparable))

        deduped = self._collapse_contained(candidates)
        if len(deduped) < MIN_ITEMS:
            return []
        return deduped[:MAX_ITEMS]

    @staticmethod
    def _collapse_contained(candidates: list[tuple[str, str]]) -> list[str]:
        """Drop items whose meaning is fully contained in another item.

        The compiler records a restriction twice — once as a scoped clause
        ("Never: log request bodies.") and once as the user's whole sentence
        ("It must not expose user emails and should never log request
        bodies."). Keeping the longer one preserves the parts of the sentence
        the scoped clause left behind.
        """
        kept: list[str] = []
        seen: list[str] = []
        # Longest first, so a container is considered before what it contains.
        for display, comparable in sorted(candidates, key=lambda c: len(c[1]), reverse=True):
            if any(comparable in existing for existing in seen):
                continue
            seen.append(comparable)
            kept.append(display)
        return kept


def render_verification_block(ir_v2: IRv2, lang: str) -> list[str]:
    """Render the checklist as system-prompt lines, or [] when there is none."""
    checklist = (ir_v2.metadata or {}).get("verification_checklist")
    if not checklist:
        return []
    heading = _HEADINGS.get(lang, _HEADINGS["en"])
    lines = [heading]
    lines.extend(f"- [ ] {item}" for item in checklist)
    return lines
