from typing import Optional
from .client import WorkerClient, WorkerResponse, DEFAULT_MODEL
from .schemas import DiagnosticItem
from app.compiler import compile_text_v2
from app.models_v2 import IRv2
from app.heuristics import detect_risk_flags

from cachetools import TTLCache


from .rag import ContextStrategist, MockVectorDB


class HybridCompiler:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.worker = WorkerClient(api_key=api_key, base_url=base_url, model=model)
        # Initialize RAG components
        self.vector_db = MockVectorDB()  # In real app, connect to actual DB
        self.context_strategist = ContextStrategist(self.vector_db, self.worker)

        # Cache: 100 items, expires in 1 hour
        self.cache = TTLCache(maxsize=100, ttl=3600)

    def compile(self, text: str) -> WorkerResponse:
        """
        Attempt to compile using the Worker LLM with RAG context.
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
            # --- RAG: Context Strategist ---
            # Retrieve relevant code context using Agent 6
            rag_context = self.context_strategist.process(text)

            # Pass context to Worker
            res = self.worker.process(text, context=rag_context)

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

                    if diag and not any(d.message == diag.message for d in res.diagnostics):
                        res.diagnostics.append(diag)
            except Exception:
                pass  # Non-critical logic

            self.cache[text] = res
            return res
        except Exception as e:
            # Log error (in a real app)
            print(f"Worker LLM failed: {e}")
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

    def generate_agent(self, text: str) -> str:
        """
        Generate a comprehensive AI Agent system prompt.
        """
        try:
            return self.worker.generate_agent(text)
        except Exception as e:
            # Fallback for agent generation
            return f"# Error\n\nFailed to generate agent: {e}"

    def generate_workspace(self, text: str) -> str:
        """
        Generate a comprehensive Workspace Configuration.
        """
        try:
            return self.worker.generate_workspace(text)
        except Exception as e:
            return f"# Error\n\nFailed to generate workspace: {e}"

    def generate_skill(self, text: str) -> str:
        """
        Generate a comprehensive AI Skill definition.
        """
        try:
            return self.worker.generate_skill(text)
        except Exception as e:
            # Fallback for skill generation
            return f"# Error\n\nFailed to generate skill: {e}"
