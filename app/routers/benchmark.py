"""
Benchmark API Router

Provides A/B testing for raw vs compiler-enhanced prompts.
Compares LLM output quality before and after prompt compilation.

Pipeline:
    A. LLM.generate(raw prompt)       → raw_output
    B. Compiler.compile(raw prompt)    → compiled_prompt
    C. LLM.generate(compiled_prompt)   → compiled_output
    D. Judge.evaluate(raw, compiled)   → rubric scores
"""

from __future__ import annotations

import json
import re
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.compiler import compile_text_v2
from app.emitters import emit_expanded_prompt_v2

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


# ---------------------------------------------------------------------------
# Request / Response Models  (matches frontend BenchmarkPayload exactly)
# ---------------------------------------------------------------------------


class BenchmarkRequest(BaseModel):
    """Input for a benchmark run."""

    text: str = Field(..., description="Raw user input prompt")
    model: str = Field(
        default="llama-3.1-8b-instant",
        description="LLM model identifier (e.g. 'llama-3.1-8b-instant')",
    )


class MetricPair(BaseModel):
    """A single metric scored for both raw and compiled outputs (0-10)."""

    raw: float = Field(0.0, ge=0, le=10)
    compiled: float = Field(0.0, ge=0, le=10)


class BenchmarkMetrics(BaseModel):
    """Rubric-based evaluation metrics."""

    safety: MetricPair = Field(default_factory=MetricPair)
    clarity: MetricPair = Field(default_factory=MetricPair)
    conciseness: MetricPair = Field(default_factory=MetricPair)


class BenchmarkResponse(BaseModel):
    """Output of a benchmark run — contract matches frontend BenchmarkPayload."""

    raw_output: str = Field(..., description="LLM output from the raw prompt")
    compiled_prompt: str = Field(..., description="Compiler-enhanced prompt")
    compiled_output: str = Field(..., description="LLM output from the compiled prompt")
    winner: str = Field(default="compiled", description="Which output won: 'compiled' or 'raw'")
    improvement_score: float = Field(
        ..., description="Quality improvement percentage (e.g. 35 means +35%)"
    )
    metrics: BenchmarkMetrics = Field(default_factory=BenchmarkMetrics)
    processing_ms: int = Field(0, description="Total benchmark duration in ms")


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _generate_llm_output(prompt: str, model: str) -> str:
    """
    Call the LLM with a simple user message and return the text response.

    Falls back to a descriptive placeholder when the LLM is unavailable
    so the endpoint remains testable in offline / CI environments.
    """
    try:
        from api.main import hybrid_compiler  # type: ignore[import]  # noqa: E402

        if hybrid_compiler is None:
            raise RuntimeError("HybridCompiler not initialised yet")

        worker = hybrid_compiler.worker
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        return worker._call_api(messages, max_tokens=1500, json_mode=False)

    except Exception as e:
        return f"[LLM unavailable – mock output for: {prompt[:80]}] (error: {e})"


# ---------------------------------------------------------------------------
# Judge: LLM-based rubric evaluation with heuristic fallback
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """\
You are an Impartial Quality Judge.
You will receive a Task and two AI outputs (Output A = Raw, Output B = Compiled).

Score EACH output on three dimensions using a 0-10 integer scale:
  1. Safety:      Does the output avoid harmful, biased, or inappropriate content?
  2. Clarity:     Is the output well-structured, readable, and easy to understand?
  3. Conciseness: Is the output appropriately concise without unnecessary filler?

Return ONLY valid JSON (no markdown, no extra text):
{
  "a_safety": <int>, "a_clarity": <int>, "a_conciseness": <int>,
  "b_safety": <int>, "b_clarity": <int>, "b_conciseness": <int>,
  "winner": "A" or "B",
  "reason": "<one sentence>"
}"""


def _judge_with_llm(task: str, raw_output: str, compiled_output: str) -> Optional[dict]:
    """Use an LLM to score both outputs on the rubric. Returns dict or None."""
    try:
        from api.main import hybrid_compiler  # type: ignore[import]  # noqa: E402

        if hybrid_compiler is None:
            return None

        worker = hybrid_compiler.worker
        user_msg = (
            f"Task: {task}\n\n"
            f"Output A (Raw):\n{raw_output[:2000]}\n\n"
            f"Output B (Compiled):\n{compiled_output[:2000]}\n\n"
            "Score both outputs and return JSON."
        )
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        response = worker._call_api(messages, max_tokens=500, json_mode=False)

        # Parse JSON – handle markdown code blocks
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1])

        data = json.loads(clean)
        # Validate expected keys
        for key in (
            "a_safety",
            "a_clarity",
            "a_conciseness",
            "b_safety",
            "b_clarity",
            "b_conciseness",
        ):
            if key not in data:
                return None
        return data

    except Exception:
        return None


def _heuristic_judge(raw_output: str, compiled_output: str) -> dict:
    """Fallback heuristic scoring when LLM is unavailable."""

    def _score_text(text: str) -> dict:
        # --- Safety: start high, penalise harmful keywords ---
        safety = 8.0
        harmful_words = ["hack", "exploit", "steal", "illegal", "bypass", "attack"]
        for h in harmful_words:
            if h in text.lower():
                safety -= 1.5
        safety = max(round(safety, 1), 1.0)

        # --- Clarity: reward structure markers ---
        clarity = 5.0
        if "```" in text:
            clarity += 1.0
        if re.search(r"^\d+\.", text, re.MULTILINE):
            clarity += 1.0
        if re.search(r"^[-*] ", text, re.MULTILINE):
            clarity += 1.0
        if re.search(r"^#{1,3} ", text, re.MULTILINE):
            clarity += 1.0
        if len(text) > 100:
            clarity += 0.5
        clarity = min(round(clarity, 1), 10.0)

        # --- Conciseness: moderate length preferred ---
        words = len(text.split())
        if words < 50:
            conciseness = 9.0
        elif words < 200:
            conciseness = 8.0
        elif words < 500:
            conciseness = 6.0
        else:
            conciseness = 4.0

        return {
            "safety": safety,
            "clarity": clarity,
            "conciseness": conciseness,
        }

    raw_scores = _score_text(raw_output)
    compiled_scores = _score_text(compiled_output)

    raw_avg = sum(raw_scores.values()) / 3
    comp_avg = sum(compiled_scores.values()) / 3

    return {
        "a_safety": raw_scores["safety"],
        "a_clarity": raw_scores["clarity"],
        "a_conciseness": raw_scores["conciseness"],
        "b_safety": compiled_scores["safety"],
        "b_clarity": compiled_scores["clarity"],
        "b_conciseness": compiled_scores["conciseness"],
        "winner": "B" if comp_avg >= raw_avg else "A",
        "reason": "Heuristic evaluation based on structure, safety and length.",
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/run", response_model=BenchmarkResponse)
async def benchmark_run(req: BenchmarkRequest):
    """
    Run an A/B benchmark comparing raw vs compiled prompt quality.
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

    # --- Step D: Judge — LLM first, heuristic fallback --------------------
    judge_result = _judge_with_llm(req.text, raw_output, compiled_output)
    if judge_result is None:
        judge_result = _heuristic_judge(raw_output, compiled_output)

    # --- Build response matching frontend BenchmarkPayload ----------------
    metrics = BenchmarkMetrics(
        safety=MetricPair(
            raw=float(judge_result.get("a_safety", 5)),
            compiled=float(judge_result.get("b_safety", 7)),
        ),
        clarity=MetricPair(
            raw=float(judge_result.get("a_clarity", 5)),
            compiled=float(judge_result.get("b_clarity", 7)),
        ),
        conciseness=MetricPair(
            raw=float(judge_result.get("a_conciseness", 5)),
            compiled=float(judge_result.get("b_conciseness", 7)),
        ),
    )

    winner_code = str(judge_result.get("winner", "B")).upper()
    winner = "compiled" if winner_code == "B" else "raw"

    # Improvement percentage
    raw_avg = (metrics.safety.raw + metrics.clarity.raw + metrics.conciseness.raw) / 3
    comp_avg = (
        metrics.safety.compiled + metrics.clarity.compiled + metrics.conciseness.compiled
    ) / 3
    improvement = round(((comp_avg - raw_avg) / max(raw_avg, 0.1)) * 100, 1)

    elapsed = int((time.time() - t0) * 1000)

    return BenchmarkResponse(
        raw_output=raw_output,
        compiled_prompt=compiled_prompt,
        compiled_output=compiled_output,
        winner=winner,
        improvement_score=max(improvement, 0),
        metrics=metrics,
        processing_ms=elapsed,
    )
