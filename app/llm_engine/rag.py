from typing import List, Dict, Any, Protocol
from dataclasses import dataclass


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
        # In a real app, this would use embeddings.
        # Here we just return dummy results or empty list.
        return []


class ContextStrategist:
    """
    Agent 6: The Context Strategist.
    Orchestrates query expansion, hybrid retrieval, and context pruning.
    """

    def __init__(self, vector_db: VectorDBConnection, llm_client):
        self.vector_db = vector_db
        self.llm = llm_client

    def expand_query(self, user_text: str) -> List[str]:
        """
        Uses LLM to expand the user's prompt into multiple search queries.
        """
        try:
            # We assume the LLM client has a method for this, or we call it generically
            # For now, let's implement a specific method in WorkerClient or use a generic one
            response = self.llm.expand_query_intent(user_text)
            return response.get("queries", [user_text])
        except Exception as e:
            print(f"[ContextStrategist] Query expansion failed: {e}")
            return [user_text]

    def retrieve(self, queries: List[str]) -> List[Snippet]:
        """
        Performs hybrid search (conceptually) using the generated queries.
        Uses Reciprocal Rank Fusion (RRF) to merge results.
        """
        all_results: Dict[str, Snippet] = {}

        # 1. Execute searches
        for q in queries:
            results = self.vector_db.search(q, limit=5)
            for i, res in enumerate(results):
                path = res.get("file_path", "unknown")
                if path in all_results:
                    # Simple score accumulation (RRF-ish)
                    # rank = i + 1, score += 1/rank
                    all_results[path].score += 1.0 / (i + 1)
                else:
                    all_results[path] = Snippet(
                        file_path=path,
                        content=res.get("content", ""),
                        score=1.0 / (i + 1),
                        metadata=res.get("metadata", {}),
                    )

        # 2. Convert to list
        snippets = list(all_results.values())

        # 3. Sort by score descending
        snippets.sort(key=lambda x: x.score, reverse=True)

        return snippets

    def rank_and_prune(self, snippets: List[Snippet], max_tokens: int = 4000) -> List[Snippet]:
        """
        Selects the top snippets that fit within the token budget.
        """
        selected = []
        current_tokens = 0

        # Simple approximation: 1 token ~= 4 chars
        for snippet in snippets:
            # Estimate token count
            tokens = len(snippet.content) // 4
            if current_tokens + tokens > max_tokens:
                continue

            selected.append(snippet)
            current_tokens += tokens

        return selected

    def process(self, user_text: str) -> Dict[str, Any]:
        """
        Main entry point for Agent 6.
        """
        # 1. Expand
        queries = self.expand_query(user_text)

        # 2. Retrieve
        raw_snippets = self.retrieve(queries)

        # 3. Prune
        final_snippets = self.rank_and_prune(raw_snippets)

        # 4. Format for context
        context_data = {
            "retrieved_files": [s.file_path for s in final_snippets],
            "snippets": [{"file": s.file_path, "content": s.content} for s in final_snippets],
        }

        return context_data
