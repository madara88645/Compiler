from __future__ import annotations

import math
import re
from typing import List

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT = re.compile(r"\s+")


def estimate_tokens(text: str) -> int:
    """Rough GPT-style token estimate (1 token ~= 4 chars or 0.75 words)."""
    if not text:
        return 0
    chars = len(text)
    words = len([w for w in _WORD_SPLIT.split(text.strip()) if w])
    return max(1, math.ceil(min(chars / 4, words / 0.75)))


def compress_text_block(text: str, max_chars: int = 600) -> str:
    """Lightweight compression: keep first sentences until limit, fall back to slice."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    sentences: List[str] = _SENTENCE_SPLIT.split(text)
    if len(sentences) <= 1:
        return text[:max_chars].rstrip() + "…"
    buf: List[str] = []
    total = 0
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        candidate = sent + " "
        if total + len(candidate) > max_chars and buf:
            break
        buf.append(sent)
        total += len(candidate)
        if total >= max_chars:
            break
    combined = " ".join(buf).strip()
    if not combined:
        combined = text[:max_chars]
    if len(combined) < len(text):
        combined = combined.rstrip() + "…"
    return combined
