"""
Context Compressor / Summarizer Module.

Provides document summarization capabilities using LLM to compress
long documents while preserving key information.
"""

from __future__ import annotations

from typing import Optional

from app.llm_engine.client import WorkerClient

# Lazy singleton client
_summarizer_client: Optional[WorkerClient] = None


def _get_client() -> WorkerClient:
    """Get or create a shared WorkerClient instance."""
    global _summarizer_client
    if _summarizer_client is None:
        _summarizer_client = WorkerClient()
    return _summarizer_client


SUMMARIZE_PROMPT = """You are a Document Summarizer. Your task is to compress the given document while preserving ALL key information.

RULES:
1. Preserve all key facts, entities, names, dates, and relationships.
2. Remove redundancy, filler words, and unnecessary elaboration.
3. Maintain the original structure if it aids understanding.
4. Use concise language without losing meaning.
5. Output ONLY the summary, no explanations or meta-commentary.

TARGET: Approximately {max_tokens} tokens or less."""


def count_tokens_approx(text: str, ratio: float = 4.0) -> int:
    """Approximate token count (chars / ratio)."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return int(len(text) / ratio)


def summarize_document(
    text: str,
    max_tokens: int = 500,
    *,
    client: Optional[WorkerClient] = None,
) -> str:
    """
    Summarize a document using LLM.

    Args:
        text: The document text to summarize.
        max_tokens: Target maximum tokens for the summary.
        client: Optional WorkerClient instance (uses shared client if None).

    Returns:
        The summarized text.
    """
    if not text or not text.strip():
        return ""

    # Skip summarization if text is already short
    original_tokens = count_tokens_approx(text)
    if original_tokens <= max_tokens:
        return text.strip()

    llm_client = client or _get_client()

    # Build prompt
    system_prompt = SUMMARIZE_PROMPT.format(max_tokens=max_tokens)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Summarize the following document:\n\n{text}"},
    ]

    try:
        # Use internal _call_api for raw text output
        summary = llm_client._call_api(messages, max_tokens=max_tokens * 2, json_mode=False)
        return summary.strip()
    except Exception as e:
        # Fallback: return truncated original on error
        print(f"[Summarizer] LLM call failed: {e}")
        # Simple truncation fallback
        words = text.split()
        approx_word_limit = max_tokens  # rough 1:1 for English
        return " ".join(words[:approx_word_limit]) + "..."


def summarize_for_ingest(
    text: str,
    max_tokens: int = 300,
    *,
    client: Optional[WorkerClient] = None,
) -> str:
    """
    Summarize a chunk for RAG ingest.

    Uses a smaller token budget suitable for chunk-level summaries.
    """
    return summarize_document(text, max_tokens=max_tokens, client=client)
