"""
Agent 6: The Context Strategist.
Responsible for semantic retrieval, query expansion, and context re-ranking.
"""
import json
import sys
from typing import List, Dict, Any, Optional
from app.rag.simple_index import search_hybrid
from app.llm_engine.client import WorkerClient


class ContextStrategist:
    """
    Agent 6: Analyzes user intent and retrieves the most relevant code context.
    """

    def __init__(self, client: Optional[WorkerClient] = None):
        self.client = client or WorkerClient()

    def retrieve(self, user_prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve context snippets relevant to the user prompt.

        Process:
        1. Analyze intent & expand queries (LLM).
        2. Search hybrid index with expanded queries.
        3. Re-rank/Filter results (heuristic for now).
        """
        # 1. Expand Query
        expanded_queries = self._expand_query(user_prompt)

        # 2. Search Index (aggregate results)
        all_results = {}

        # Search for original prompt (high weight)
        base_results = search_hybrid(user_prompt, k=limit)
        for r in base_results:
            r["score"] = r.get("score", 0) * 1.5  # Boost original query
            all_results[r["path"]] = r

        # Search for expanded queries
        for q in expanded_queries:
            sub_results = search_hybrid(q, k=3)
            for r in sub_results:
                if r["path"] in all_results:
                    # Boost existing (confirmation)
                    all_results[r["path"]]["score"] += 0.2
                else:
                    all_results[r["path"]] = r

        # 3. Sort & Limit
        sorted_results = sorted(all_results.values(), key=lambda x: x.get("score", 0), reverse=True)

        return sorted_results[:limit]

    def _expand_query(self, prompt: str) -> List[str]:
        """
        Use LLM to generate 3 semantic search queries based on the prompt.
        """
        system_msg = (
            "You are an expert researcher and technical strategist. Analyze the user request and generate "
            "3 specific search queries to find relevant information (code snippets, knowledge base entries, documentation) "
            "in the provided context.\n"
            'Return ONLY a JSON list of strings. Example: ["auth middleware", "brand color guidelines", "database schema"]'
        )

        try:
            response = self.client._call_api(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Request: {prompt}"},
                ],
                max_tokens=100,
                json_mode=True,
            )
            data = json.loads(response)
            if isinstance(data, list):
                return data[:3]
            return []
        except Exception as e:
            print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)
            return []
