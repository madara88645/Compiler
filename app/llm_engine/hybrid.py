from typing import Optional
from .client import WorkerClient, WorkerResponse, DEFAULT_MODEL
from .schemas import DiagnosticItem
from app.compiler import compile_text_v2
from app.models_v2 import IRv2

from cachetools import TTLCache

class HybridCompiler:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.worker = WorkerClient(api_key=api_key, base_url=base_url, model=model)
        # Cache: 100 items, expires in 1 hour
        self.cache = TTLCache(maxsize=100, ttl=3600)

    def compile(self, text: str) -> WorkerResponse:
        """
        Attempt to compile using the Worker LLM.
        Falls back to local heuristics if LLM fails.
        """
        # 1. Fast Checks (Heuristic Guardrails)
        if not text or not text.strip():
            return self._fallback(text, "Input was empty")
            
        # 2. Check Cache
        if text in self.cache:
            return self.cache[text]

        # 3. Worker LLM (Slow but Smart)
        try:
            res = self.worker.process(text)
            self.cache[text] = res
            return res
        except Exception as e:
            # Log error (in a real app)
            # print(f"Worker LLM failed: {e}")
            return self._fallback(text, str(e))

    def _fallback(self, text: str, error_msg: str) -> WorkerResponse:
        """
        Generate a partial response using legacy heuristics.
        """
        try:
            # Use existing heuristic compiler
            ir = compile_text_v2(text)
            
            # Create a simple diagnostic for the fallback
            diag = DiagnosticItem(
                severity="warning",
                message=f"Running in offline/heuristic mode. LLM Engine error: {error_msg}",
                suggestion="Check your API Key or network connection.",
                category="system"
            )
            
            # Simple Expanded Prompt generation (since we don't have the LLM's optimized content)
            # We could use a template renderer here, but for now just return a placeholder.
            optimized = (
                f"# Request Analysis (Offline)\n\n"
                f"**System Note**: This prompt was compiled using local heuristics because the LLM worker failed.\n\n"
                f"## Extracted Constraints\n" +
                "\n".join([f"- {c.text}" for c in ir.constraints])
            )

            return WorkerResponse(
                ir=ir,
                diagnostics=[diag],
                thought_process="Fallback to heuristics due to LLM error.",
                optimized_content=optimized
            )
        except Exception as e:
            # Absolute worst case if heuristics fail too
             return WorkerResponse(
                ir=IRv2(
                    language="en", persona="assistant", role="Helpful Assistant", domain="general",
                    output_format="text", length_hint="medium"
                ),
                diagnostics=[DiagnosticItem(severity="error", message=f"Critical system failure: {e}", category="system")],
                thought_process="System Failure",
                optimized_content="Error."
            )
