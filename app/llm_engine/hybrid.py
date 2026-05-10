import logging
from typing import Any, Optional
from .client import WorkerClient, WorkerResponse, DEFAULT_MODEL
from .schemas import DiagnosticItem
from app.compiler import compile_text_v2
from app.models_v2 import IRv2
from app.heuristics import detect_risk_flags

from cachetools import TTLCache

from .rag import ContextStrategist, SQLiteVectorDB
import os

logger = logging.getLogger("promptc.llm.hybrid")
_WORKER_MAX_ATTEMPTS = 2


class HybridCompiler:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.worker = WorkerClient(api_key=api_key, base_url=base_url, model=model)
        self.default_mode = (
            (os.environ.get("PROMPT_COMPILER_MODE") or "conservative").strip().lower()
        )
        # Initialize RAG components
        self.vector_db = SQLiteVectorDB()
        self.context_strategist = ContextStrategist(self.vector_db, self.worker)

        # Cache: 100 items, expires in 1 hour
        self.cache = TTLCache(maxsize=100, ttl=3600)

    def compile(self, text: str, mode: Optional[str] = None) -> WorkerResponse:
        """
        Attempt to compile using the Worker LLM with RAG context.
        Falls back to local heuristics if LLM fails.
        """
        # 1. Fast Checks (Heuristic Guardrails)
        if not text or not text.strip():
            return self._fallback(text, "Input was empty")

        # 2. Check Cache
        cache_key = (text, (mode or self.default_mode or "conservative").strip().lower())
        if cache_key in self.cache:
            return self.cache[cache_key]

        # 3. Worker LLM (Slow but Smart)
        try:
            # --- RAG: Context Strategist ---
            # Retrieve relevant code context using Agent 6
            rag_context = self.context_strategist.process(text)

            # Pass context to Worker. Retry once for transient worker/API failures before
            # dropping to the deterministic heuristic fallback.
            resolved_mode = mode or self.default_mode
            for attempt in range(1, _WORKER_MAX_ATTEMPTS + 1):
                try:
                    res = self.worker.process(text, context=rag_context, mode=resolved_mode)
                    break
                except Exception as e:
                    if attempt < _WORKER_MAX_ATTEMPTS:
                        logger.warning(
                            "Worker LLM attempt failed",
                            exc_info=True,
                            extra={
                                "mode": resolved_mode,
                                "text_length": len(text),
                                "attempt": attempt,
                                "max_attempts": _WORKER_MAX_ATTEMPTS,
                                "rag_context_available": bool(rag_context),
                            },
                        )
                        continue

                    logger.warning(
                        "Worker LLM failed; using heuristic fallback",
                        exc_info=True,
                        extra={
                            "mode": resolved_mode,
                            "text_length": len(text),
                            "attempts": attempt,
                            "rag_context_available": bool(rag_context),
                        },
                    )
                    return self._fallback(text, f"{e} after {attempt} attempts")

            # --- Safety Heuristics Check (Post-Processing) ---
            # Even if LLM is smart, we enforce safety flags via heuristics
            try:
                flags = detect_risk_flags(text)
                for flag in flags:
                    diag = None
                    if flag == "health":
                        diag = DiagnosticItem(
                            severity="warning",
                            message="⚠️ Medical/Health topic detected.",
                            suggestion="Content for informational use only. No medical advice.",
                            category="safety",
                        )
                    elif flag == "financial":
                        diag = DiagnosticItem(
                            severity="warning",
                            message="⚠️ Financial/Crypto topic detected.",
                            suggestion="Do not provide investment advice. Treat as general info.",
                            category="safety",
                        )
                    elif flag == "legal":
                        diag = DiagnosticItem(
                            severity="warning",
                            message="⚠️ Legal topic detected.",
                            suggestion="Do not provide legal counsel. Consult a lawyer.",
                            category="safety",
                        )
                    elif flag == "security":
                        diag = DiagnosticItem(
                            severity="info",
                            message="🛡️ Security topic detected.",
                            suggestion="Follow ethical hacking guidelines.",
                            category="safety",
                        )

                    if diag:
                        # Bolt Optimization: Replace any() generator expression with fast-path loop
                        diag_found = False
                        for d in res.diagnostics:
                            if d.message == diag.message:
                                diag_found = True
                                break
                        if not diag_found:
                            res.diagnostics.append(diag)
            except Exception:
                logger.warning(
                    "Safety post-processing failed; continuing without extra risk diagnostics",
                    exc_info=True,
                    extra={"mode": resolved_mode, "text_length": len(text)},
                )

            self.cache[cache_key] = res
            return res
        except Exception as e:
            logger.warning(
                "Worker LLM failed before worker response; using heuristic fallback",
                exc_info=True,
                extra={
                    "mode": mode or self.default_mode,
                    "text_length": len(text),
                    "attempts": 0,
                    "rag_context_available": False,
                },
            )
            return self._fallback(text, str(e))

    def _fallback(self, text: str, error_msg: str) -> WorkerResponse:
        """
        Generate a partial response using legacy heuristics.
        """
        try:
            # Use existing heuristic compiler (which runs RiskHandler)
            ir = compile_text_v2(text)

            # Create a simple diagnostic for the fallback
            system_diag = DiagnosticItem(
                severity="warning",
                message=f"Running in offline/heuristic mode. LLM Engine error: {error_msg}",
                suggestion="Check your API Key or network connection.",
                category="system",
            )

            # Merge diagnostics (IRv2 diagnostics from RiskHandler + System warning)
            all_diags = ir.diagnostics + [system_diag]

            # Simple Expanded Prompt generation (since we don't have the LLM's optimized content)
            optimized = (
                "# Request Analysis (Offline)\n\n"
                "**System Note**: This prompt was compiled using local heuristics because the LLM worker failed.\n\n"
                "## Extracted Constraints\n" + "\n".join([f"- {c.text}" for c in ir.constraints])
            )

            return WorkerResponse(
                ir=ir,
                diagnostics=all_diags,
                thought_process="Fallback to heuristics due to LLM error.",
                optimized_content=optimized,
            )
        except Exception as e:
            # Absolute worst case if heuristics fail too
            return WorkerResponse(
                ir=IRv2(
                    language="en",
                    persona="assistant",
                    role="Helpful Assistant",
                    domain="general",
                    output_format="text",
                    length_hint="medium",
                ),
                diagnostics=[
                    DiagnosticItem(
                        severity="error", message=f"Critical system failure: {e}", category="system"
                    )
                ],
                thought_process="System Failure",
                optimized_content="Error.",
            )

    def generate_agent(
        self,
        text: str,
        multi_agent: bool = False,
        include_example_code: bool = False,
        repo_context: dict[str, Any] | None = None,
        repo_context_mode: str = "full",
    ) -> str:
        """
        Generate a comprehensive AI Agent system prompt, aware of RAG context.
        """
        try:
            # Retrieve relevant code context using Agent 6
            rag_context = self._merge_generator_context(
                self.context_strategist.process(text),
                repo_context,
                repo_context_mode,
            )
            return self.worker.generate_agent(
                text,
                context=rag_context,
                multi_agent=multi_agent,
                include_example_code=include_example_code,
            )
        except Exception as e:
            # Fallback for agent generation
            return f"# Error\n\nFailed to generate agent: {e}"

    def generate_skill(
        self,
        text: str,
        include_example_code: bool = False,
        repo_context: dict[str, Any] | None = None,
        repo_context_mode: str = "full",
    ) -> str:
        """
        Generate a comprehensive AI Skill definition, aware of RAG context.
        """
        try:
            # Retrieve relevant code context using Agent 6
            rag_context = self._merge_generator_context(
                self.context_strategist.process(text),
                repo_context,
                repo_context_mode,
            )
            return self.worker.generate_skill(
                text,
                context=rag_context,
                include_example_code=include_example_code,
            )
        except Exception as e:
            # Fallback for skill generation
            return f"# Error\n\nFailed to generate skill: {e}"

    def _merge_generator_context(
        self,
        rag_context: Any,
        repo_context: dict[str, Any] | None,
        repo_context_mode: str = "full",
    ) -> Any:
        """
        Merge an optional repo_context payload into the existing RAG context.

        rag_context is whatever ``ContextStrategist.process`` returned and may be a
        dict, a string, or None depending on configuration. When no repo_context
        is supplied this method passes rag_context through unchanged so existing
        non-dict callers keep working; only when wrapping repo_context do we coerce
        rag_context into a dict.
        """
        if not repo_context:
            return rag_context
        merged: dict[str, Any] = dict(rag_context) if isinstance(rag_context, dict) else {}
        mode = (repo_context_mode or "full").strip().lower()
        if mode not in {"full", "compact"}:
            mode = "full"
        merged["repo_context"] = {
            "source": "github_public_repo",
            "mode": mode,
            **repo_context,
        }
        return merged
