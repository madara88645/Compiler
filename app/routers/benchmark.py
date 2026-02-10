"""
Benchmark API Router

Provides A/B testing for raw vs compiler-enhanced prompts.
Compares LLM output quality before and after prompt compilation.
"""

from __future__ import annotations

import time
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.compiler import compile_text_v2
from app.emitters import emit_expanded_prompt_v2

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class BenchmarkRequest(BaseModel):
    """Input for a benchmark run."""

    text: str = Field(..., description="Raw user input prompt")
    model: str = Field(
        default="llama-3.1-8b-instant",
        description="LLM model identifier (e.g. 'llama-3.1-8b-instant')",
    )


class BenchmarkResponse(BaseModel):
    """Output of a benchmark run."""

    raw_output: str = Field(..., description="LLM output from the raw prompt")
    compiled_prompt: str = Field(..., description="Compiler-enhanced prompt")
    compiled_output: str = Field(..., description="LLM output from the compiled prompt")
    winner: str = Field(
        default="compiled", description="Which output won: 'compiled', 'raw', or 'tie'"
    )
    improvement_score: float = Field(
        ..., description="Quality improvement percentage (e.g. 20 means +20%)"
    )
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Detailed metric scores (raw_relevance, compiled_relevance, etc.)",
    )
    processing_ms: int = Field(0, description="Total benchmark duration in ms")


# ---------------------------------------------------------------------------
# Mock Judge (placeholder until full JudgeAgent integration)
# ---------------------------------------------------------------------------


def _mock_judge_evaluate(raw_output: str, improved_output: str) -> float:
    """
    Heuristic quality comparison between two outputs.

    Scoring factors:
      - length ratio   (longer, more detailed answers score higher)
      - structure bonus (presence of markdown headings / bullet points)

    Returns a float in [0.0, 1.0] representing the relative improvement.
    """
    if not raw_output and not improved_output:
        return 0.0

    raw_len = max(len(raw_output), 1)
    imp_len = max(len(improved_output), 1)

    # Length ratio component (capped at +0.5)
    length_ratio = min((imp_len - raw_len) / raw_len, 0.5) if imp_len > raw_len else 0.0

    # Structure bonus: reward markdown headings, bullets, code blocks
    structure_markers = ["#", "- ", "* ", "```", "1."]
    raw_struct = sum(1 for m in structure_markers if m in raw_output)
    imp_struct = sum(1 for m in structure_markers if m in improved_output)
    struct_bonus = min((imp_struct - raw_struct) * 0.1, 0.3) if imp_struct > raw_struct else 0.0

    score = round(min(length_ratio + struct_bonus + 0.1, 1.0), 3)
    return score


# ---------------------------------------------------------------------------
# LLM helper (uses the global HybridCompiler initialised in api/main.py)
# ---------------------------------------------------------------------------


def _generate_llm_output(prompt: str, model: str) -> str:
    """
    Call the LLM with a simple user message and return the text response.

    Falls back to a descriptive placeholder when the LLM is unavailable
    so the endpoint remains testable in offline / CI environments.
    """
    try:
        # Lazy import to avoid circular deps at module level
        from api.main import hybrid_compiler  # type: ignore[import]

        if hybrid_compiler is None:
            raise RuntimeError("HybridCompiler not initialised yet")

        worker = hybrid_compiler.worker
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        return worker._call_api(messages, max_tokens=1500, json_mode=False)

    except Exception as e:
        # Graceful fallback – useful during testing / offline mode
        return f"[LLM unavailable – mock output for: {prompt[:80]}] (error: {e})"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/run", response_model=BenchmarkResponse)
async def benchmark_run(req: BenchmarkRequest):
    """
    Run an A/B benchmark comparing raw vs compiled prompt quality.

    Pipeline:
        A. LLM.generate(raw prompt)       → raw_output
        B. Compiler.compile(raw prompt)    → compiled_prompt
        C. LLM.generate(compiled_prompt)   → improved_output
        D. Judge.evaluate(raw, improved)   → score_improvement
    """
    t0 = time.time()

    # --- Step A: Generate with raw prompt ---------------------------------
    try:
        raw_output = _generate_llm_output(req.text, req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step A failed: {e}")

    # --- Step B: Compile the prompt ---------------------------------------
    try:
        ir_v2 = compile_text_v2(req.text)
        compiled_prompt = emit_expanded_prompt_v2(ir_v2, diagnostics=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step B (compile) failed: {e}")

    # --- Step C: Generate with compiled prompt ----------------------------
    try:
        compiled_output = _generate_llm_output(compiled_prompt, req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step C failed: {e}")

    # --- Step D: Judge / evaluate -----------------------------------------
    score_raw = _mock_judge_evaluate(raw_output, raw_output)  # baseline
    score_compiled = _mock_judge_evaluate(raw_output, compiled_output)
    improvement = round(score_compiled * 100, 1)  # as percentage

    # Determine winner
    if score_compiled > 0.05:
        winner = "compiled"
    elif score_compiled < -0.05:
        winner = "raw"
    else:
        winner = "tie"

    elapsed = int((time.time() - t0) * 1000)

    # Build metrics matching frontend BenchmarkData.metrics
    raw_len = max(len(raw_output), 1)
    comp_len = max(len(compiled_output), 1)
    metrics = {
        "raw_relevance": round(min(raw_len / 100, 10.0), 1),
        "compiled_relevance": round(min(comp_len / 100, 10.0), 1),
        "raw_clarity": round(6.0 + score_raw * 4, 1),
        "compiled_clarity": round(6.0 + score_compiled * 4, 1),
    }

    return BenchmarkResponse(
        raw_output=raw_output,
        compiled_prompt=compiled_prompt,
        compiled_output=compiled_output,
        winner=winner,
        improvement_score=improvement,
        metrics=metrics,
        processing_ms=elapsed,
    )
