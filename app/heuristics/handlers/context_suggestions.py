"""
Context Suggestion Handler.

Heuristically suggests files from the RAG index that might be relevant to the
user's prompt based on keyword matching.
"""

from __future__ import annotations

import re
from typing import List, Dict
from pathlib import Path

from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2
from app.rag.simple_index import get_all_indexed_files, DEFAULT_DB_PATH


class ContextSuggestionHandler(BaseHandler):
    """
    Scans the prompt for keywords that match filenames in the RAG index.
    """

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        try:
            indexed_files = get_all_indexed_files(DEFAULT_DB_PATH)
        except Exception:
            # If DB is locked or unavailable, skip suggestions silently
            return

        if not indexed_files:
            return

        prompt_text = (ir_v1.metadata or {}).get("original_text", "")
        if not prompt_text:
            return

        suggestions = self._find_suggestions(prompt_text, indexed_files)

        if suggestions:
            ir_v2.metadata = ir_v2.metadata or {}
            ir_v2.metadata["context_suggestions"] = suggestions

    def _find_suggestions(self, text: str, file_paths: List[str]) -> List[Dict[str, str]]:
        """
        Identify files whose names appear in the text.
        Returns a list of dicts: {"path": str, "reason": str}
        """
        suggestions = []
        text_lower = text.lower()

        # 1. Exact Filename Match (e.g. "Take a look at auth.py")
        # 2. Stem Match (e.g. "Fix the auth logic") -> matches auth.py

        seen_paths = set()

        for path_str in file_paths:
            path = Path(path_str)
            filename = path.name.lower()
            stem = path.stem.lower()

            # Skip very short stems to avoid noise (e.g. "ui", "id", "db" are common words)
            if len(stem) < 3:
                continue

            # Check for exact filename
            if filename in text_lower:
                if path_str not in seen_paths:
                    suggestions.append(
                        {"path": path_str, "name": path.name, "reason": f"Mentioned '{filename}'"}
                    )
                    seen_paths.add(path_str)
                continue

            # Check for stem as a distinct word
            # Use regex word boundary to avoid matching "authentication" with "auth" if strictness desired
            # But "auth" is often a prefix. Let's stick to word boundaries for precision.
            if re.search(r"\b" + re.escape(stem) + r"\b", text_lower):
                if path_str not in seen_paths:
                    suggestions.append(
                        {"path": path_str, "name": path.name, "reason": f"Topic '{stem}' detected"}
                    )
                    seen_paths.add(path_str)

        # Cap suggestions to avoid overwhelming the user
        return suggestions[:5]
