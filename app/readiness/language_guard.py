from __future__ import annotations

from app.heuristics import detect_language


def output_language_mismatch(input_text: str, output_text: str) -> bool:
    """True when a non-English input produced an output in a different language.

    English is the project's default language and is never overridden, so an
    English input always returns False.
    """
    if not input_text or not output_text:
        return False
    in_lang = detect_language(input_text)
    if in_lang == "en":
        return False
    return detect_language(output_text) != in_lang
