from __future__ import annotations

import math
import re
from typing import List

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str, token_ratio: float = 4.0) -> int:
    """Estimate tokens from text size and words, without provider exactness.

    This is deliberately labelled an estimate: provider tokenizers differ and
    chat-message overhead is not represented. ``token_ratio`` applies to ASCII
    characters (UTF-8 bytes for other scripts), avoiding tiny word-count caps
    for CJK text and minified code when a tokenizer is unavailable.
    """
    if not text:
        return 0
    size = len(text.encode("utf-8", errors="replace"))
    try:
        ratio = float(token_ratio)
    except (TypeError, ValueError):
        ratio = 4.0
    if not math.isfinite(ratio) or ratio <= 0:
        ratio = 4.0
    words = len(text.split())
    # Word boundaries must never cap the estimate for long identifiers, CJK
    # paragraphs or code separated by just a few newlines.
    return max(1, math.ceil(max(size / ratio, words)))


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
