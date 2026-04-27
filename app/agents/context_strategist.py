"""
Agent 6: The Context Strategist.
Responsible for semantic retrieval, query expansion, and context re-ranking.
"""
import json
import re
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
            if q.strip().lower() == user_prompt.strip().lower():
                continue
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
            "Do not invent filenames, functions, endpoints, or API names unless they appear in the user request.\n"
            'Return ONLY a JSON list of strings. Example: ["login page 500 password", "password validation error handling", "authentication form special characters"]'
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
            return self._normalize_queries(data, prompt)
        except Exception as e:
            print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)
            return self._normalize_queries([], prompt)

    _ARTIFACT_LIKE_RE = re.compile(
        r"(?:\b[A-Za-z_]\w*\.[A-Za-z_]\w*\b|\b[A-Za-z_]\w*_[A-Za-z_]\w*\b|\b[\w.-]+\.(?:py|ts|tsx|js|jsx|md|json|ya?ml|toml|sql)\b)"
    )

    @classmethod
    def _normalize_queries(cls, data: Any, original_query: str = "") -> List[str]:
        if isinstance(data, dict):
            data = data.get("queries")
        if not isinstance(data, list):
            data = []

        queries: List[str] = []
        seen: set[str] = set()

        def add_query(value: str) -> None:
            query = " ".join(value.strip().split())
            if not query:
                return
            key = query.lower()
            if key in seen:
                return
            if cls._looks_like_invented_artifact(query, original_query):
                return
            seen.add(key)
            queries.append(query)

        if original_query:
            add_query(original_query)

        for item in data:
            if not isinstance(item, str):
                continue
            add_query(item)
            if len(queries) >= 3:
                break
        return queries

    @classmethod
    def _looks_like_invented_artifact(cls, query: str, original_query: str) -> bool:
        if not cls._ARTIFACT_LIKE_RE.search(query):
            return False
        return query.lower() not in original_query.lower()
