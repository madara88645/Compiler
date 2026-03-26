from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from app.rag.simple_index import search, search_hybrid

logger = logging.getLogger("promptc.llm.rag")


class VectorDBConnection(Protocol):
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        ...


@dataclass
class Snippet:
    file_path: str
    content: str
    score: float
    metadata: Dict[str, Any]


class MockVectorDB:
    """Simulates a vector DB for testing or standalone mode."""

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return []


class SQLiteVectorDB:
    """Thin adapter over the local SQLite RAG index."""

    def __init__(self, db_path: Optional[str] = None, embed_dim: int = 64, alpha: float = 0.35):
        self.db_path = db_path
        self.embed_dim = embed_dim
        self.alpha = alpha

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            results = search_hybrid(
                query,
                k=limit,
                db_path=self.db_path,
                embed_dim=self.embed_dim,
                alpha=self.alpha,
            )
        except Exception:
            results = search(query, k=limit, db_path=self.db_path)

        mapped: List[Dict[str, Any]] = []
        for item in results:
            mapped.append(
                {
                    "file_path": item.get("path", "unknown"),
                    "content": item.get("snippet", ""),
                    "score": float(
                        item.get(
                            "hybrid_score",
                            item.get("similarity", 1.0 - float(item.get("score", 0.0) or 0.0)),
                        )
                    ),
                    "metadata": {
                        "chunk_index": item.get("chunk_index"),
                        "chunk_id": item.get("chunk_id"),
                    },
                }
            )
        return mapped


class ContextStrategist:
    """
    Agent 6: The Context Strategist.
    Orchestrates query expansion, hybrid retrieval, and context pruning.
    """

    def __init__(self, vector_db: VectorDBConnection, llm_client):
        self.vector_db = vector_db
        self.llm = llm_client

    def expand_query(self, user_text: str) -> List[str]:
        try:
            response = self.llm.expand_query_intent(user_text)
            return response.get("queries", [user_text])
        except Exception as exc:
            logger.debug("Query expansion failed: %s", exc)
            return [user_text]

    def retrieve(self, queries: List[str]) -> List[Snippet]:
        all_results: Dict[str, Snippet] = {}

        for query in queries:
            results = self.vector_db.search(query, limit=5)
            for index, result in enumerate(results):
                path = result.get("file_path", "unknown")
                if path in all_results:
                    all_results[path].score += 1.0 / (index + 1)
                else:
                    all_results[path] = Snippet(
                        file_path=path,
                        content=result.get("content", ""),
                        score=1.0 / (index + 1),
                        metadata=result.get("metadata", {}),
                    )

        snippets = list(all_results.values())
        snippets.sort(key=lambda item: item.score, reverse=True)
        return snippets

    def rank_and_prune(self, snippets: List[Snippet], max_tokens: int = 4000) -> List[Snippet]:
        selected: List[Snippet] = []
        current_tokens = 0

        for snippet in snippets:
            tokens = len(snippet.content) // 4
            if current_tokens + tokens > max_tokens:
                continue
            selected.append(snippet)
            current_tokens += tokens

        return selected

    def process(self, user_text: str) -> Dict[str, Any]:
        queries = self.expand_query(user_text)
        raw_snippets = self.retrieve(queries)
        final_snippets = self.rank_and_prune(raw_snippets)

        return {
            "retrieved_files": [snippet.file_path for snippet in final_snippets],
            "snippets": [
                {"file": snippet.file_path, "content": snippet.content}
                for snippet in final_snippets
            ],
            "retrieval_status": "ok" if final_snippets else "empty",
            "retrieval_note": (
                f"Retrieved {len(final_snippets)} context snippets."
                if final_snippets
                else "No indexed context available."
            ),
        }
