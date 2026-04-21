from __future__ import annotations

import time
import functools
import uuid
import anyio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from api.auth import APIKey, verify_api_key, verify_api_key_if_required
from api.shared import forced_minimal_expanded_prompt, is_meta_leaked, logger, resolve_mode
from app.compiler import HEURISTIC_VERSION, HEURISTIC2_VERSION
from app.compiler import compile_text, compile_text_v2, generate_trace, optimize_ir
from app.emitters import (
    emit_expanded_prompt,
    emit_expanded_prompt_v2,
    emit_plan,
    emit_plan_v2,
    emit_system_prompt,
    emit_system_prompt_v2,
    emit_user_prompt,
    emit_user_prompt_v2,
)
from app.llm_engine.schemas import QualityReport
from app.models_v2 import DiagnosticItem, IRv2
from app.optimizer.language_costs import DEFAULT_GROQ_MODEL, detect_language, estimate_prompt_cost
from app.optimizer.postprocess import strip_wrapper_labels

router = APIRouter(tags=["compile"])

_MAX_PROMPT_CHARS = 20_000


def _get_compiler():
    from api import main as api_main

    return api_main.get_compiler()


class ValidateRequest(BaseModel):
    text: str = Field(default="", max_length=_MAX_PROMPT_CHARS)
    include_suggestions: bool = Field(default=True, description="Include improvement suggestions")
    include_strengths: bool = Field(default=True, description="Include identified strengths")


class CompileRequest(BaseModel):
    text: str = Field(default="", max_length=_MAX_PROMPT_CHARS)
    diagnostics: bool = False
    trace: bool = False
    v2: bool = True
    render_v2_prompts: bool = False
    record_analytics: bool = False
    user_level: str = Field(default="intermediate", max_length=100)
    task_type: str = Field(default="general", max_length=100)
    tags: Optional[List[str]] = Field(default=None, max_length=50)
    mode: Optional[str] = Field(
        default=None,
        max_length=40,
        description='Optional prompt compiler mode, e.g. "conservative" or "default".',
    )

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, tags: Optional[List[str]]) -> Optional[List[str]]:
        if tags is None:
            return None
        normalized = [tag.strip() for tag in tags if tag and tag.strip()]
        return normalized[:20]


class CompileResponse(BaseModel):
    ir: dict
    ir_v2: dict | None = None
    system_prompt: str
    user_prompt: str
    plan: str
    expanded_prompt: str
    system_prompt_v2: str | None = None
    user_prompt_v2: str | None = None
    plan_v2: str | None = None
    expanded_prompt_v2: str | None = None
    processing_ms: int
    request_id: str
    heuristic_version: str
    heuristic2_version: str | None = None
    trace: list[str] | None = None
    critique: dict | None = None


class OptimizeRequest(BaseModel):
    text: str = Field(default="", max_length=_MAX_PROMPT_CHARS)
    max_chars: Optional[int] = Field(default=None, ge=1, le=_MAX_PROMPT_CHARS)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8_000)
    token_ratio: float = Field(default=4.0, gt=0, le=20.0)
    provider: str = Field(default="groq", max_length=40)
    model: Optional[str] = Field(default=None, max_length=120)


class OptimizeResponse(BaseModel):
    text: str
    before_chars: int
    after_chars: int
    before_tokens: int
    after_tokens: int
    saved_percent: float
    passes: int
    met_max_chars: bool
    met_max_tokens: bool
    met_budget: bool
    changed: bool
    provider: str
    model: str
    source_language: str
    tokenizer_method: str
    estimated_input_cost_usd: float
    estimated_output_cost_usd: float
    estimated_savings_usd: float
    english_variant: str
    english_variant_tokens: int
    english_variant_cost_usd: float
    warnings: list[str]
    optimizer_call_usage: dict | None = None


def _safe_worker_text(worker_res, field_name: str) -> str:
    value = getattr(worker_res, field_name, "")
    if not isinstance(value, str):
        return ""
    return value if field_name == "plan" or not is_meta_leaked(value) else ""


def _warning_for_fast_fallback(reason: str) -> DiagnosticItem:
    return DiagnosticItem(
        severity="warning",
        message=f"Running in offline/heuristic mode. Fast compiler worker issue: {reason}",
        suggestion="Retry after checking the worker API key, network, or model response shape.",
        category="system",
    )


def _coerce_fast_ir(text: str, worker_res, fallback_reason: str | None = None) -> tuple[IRv2, bool]:
    candidate = getattr(worker_res, "ir", None) if worker_res is not None else None

    if isinstance(candidate, IRv2):
        ir2 = candidate
        used_fallback = False
    else:
        raw_ir = None
        if isinstance(candidate, dict):
            raw_ir = candidate
        elif hasattr(candidate, "model_dump"):
            try:
                raw_ir = candidate.model_dump()
            except Exception as exc:
                fallback_reason = fallback_reason or f"IR serialization failed: {exc}"

        if isinstance(raw_ir, dict) and raw_ir:
            try:
                ir2 = IRv2.model_validate(raw_ir)
                used_fallback = False
            except Exception as exc:
                fallback_reason = fallback_reason or f"IR validation failed: {exc}"
                ir2 = compile_text_v2(text, offline_only=True)
                used_fallback = True
        else:
            fallback_reason = fallback_reason or "worker result was empty or missing ir"
            ir2 = compile_text_v2(text, offline_only=True)
            used_fallback = True

    if used_fallback:
        ir2.diagnostics.append(_warning_for_fast_fallback(fallback_reason or "unknown error"))

    return ir2, used_fallback


def _fast_compile_payload(
    req: CompileRequest,
    worker_res,
    mode: str,
    start: float,
    fallback_reason: str | None = None,
) -> tuple[dict, bool]:
    ir2, used_fallback = _coerce_fast_ir(req.text, worker_res, fallback_reason)

    system_prompt = _safe_worker_text(worker_res, "system_prompt") or emit_system_prompt_v2(ir2)
    user_prompt = _safe_worker_text(worker_res, "user_prompt") or emit_user_prompt_v2(ir2)
    plan = _safe_worker_text(worker_res, "plan") or emit_plan_v2(ir2)
    optimized_content = _safe_worker_text(worker_res, "optimized_content")

    forced_expanded = None
    if mode != "default":
        forced_expanded = forced_minimal_expanded_prompt(req.text, ir2, req.diagnostics)

    expanded_prompt = (
        forced_expanded
        or optimized_content
        or emit_expanded_prompt_v2(ir2, diagnostics=req.diagnostics)
    )
    ir_dump = ir2.model_dump()

    return (
        {
            "ir": ir_dump,
            "ir_v2": ir_dump,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "plan": plan,
            "expanded_prompt": expanded_prompt,
            "system_prompt_v2": system_prompt,
            "user_prompt_v2": user_prompt,
            "plan_v2": plan,
            "expanded_prompt_v2": expanded_prompt,
            "processing_ms": int((time.time() - start) * 1000),
            "request_id": "fast_" + uuid.uuid4().hex[:12],
            "heuristic_version": "v2-fast",
            "heuristic2_version": "v2-fast",
            "trace": [],
            "critique": None,
        },
        used_fallback,
    )


@router.post("/compile", response_model=CompileResponse)
def compile_endpoint(
    req: CompileRequest,
    request: Request,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    t0 = time.time()
    rid = uuid.uuid4().hex[:12]

    ir = optimize_ir(compile_text(req.text))
    trace_lines = generate_trace(ir) if req.trace else None
    ir2 = compile_text_v2(req.text, offline_only=not req.v2)

    sys_v2 = user_v2 = plan_v2 = exp_v2 = None
    mode = resolve_mode(req.mode, request)

    if req.v2:
        try:
            compiler = _get_compiler()
            worker_res = compiler.compile(req.text, mode=mode)
            ir2 = worker_res.ir

            if worker_res.system_prompt and not is_meta_leaked(worker_res.system_prompt):
                sys_v2 = worker_res.system_prompt
            if worker_res.user_prompt and not is_meta_leaked(worker_res.user_prompt):
                user_v2 = worker_res.user_prompt
            if worker_res.plan:
                plan_v2 = worker_res.plan
            if worker_res.optimized_content and not is_meta_leaked(worker_res.optimized_content):
                exp_v2 = worker_res.optimized_content
        except Exception as exc:
            logger.warning("LLM compile failed; falling back to local v2 heuristics: %s", exc)

    if mode != "default":
        forced_expanded = forced_minimal_expanded_prompt(req.text, ir2, req.diagnostics)
        if forced_expanded:
            exp_v2 = forced_expanded

    if req.render_v2_prompts and ir2 is not None:
        sys_v2 = sys_v2 or emit_system_prompt_v2(ir2)
        user_v2 = user_v2 or emit_user_prompt_v2(ir2)
        plan_v2 = plan_v2 or emit_plan_v2(ir2)
        exp_v2 = exp_v2 or emit_expanded_prompt_v2(ir2, diagnostics=req.diagnostics)

    critique_result = None
    if sys_v2:
        try:
            from app.optimizer.critic import CriticAgent

            critic = CriticAgent()
            context_str = ""
            if ir2 and ir2.metadata.get("context_snippets"):
                snippets = ir2.metadata["context_snippets"]
                context_str = "\n\n".join(
                    [
                        f"--- File: {item.get('path')} ---\n{item.get('snippet', '')}"
                        for item in snippets
                    ]
                )
            critique_result = critic.critique(
                user_request=req.text,
                system_prompt=sys_v2,
                context=context_str,
            ).model_dump()
        except Exception as exc:
            logger.debug("Critique generation skipped: %s", exc)

    elapsed = int((time.time() - t0) * 1000)

    return CompileResponse(
        ir=ir.model_dump(),
        ir_v2=(ir2.model_dump() if ir2 else None),
        system_prompt=emit_system_prompt(ir),
        user_prompt=emit_user_prompt(ir),
        plan=emit_plan(ir),
        expanded_prompt=emit_expanded_prompt(
            ir,
            diagnostics=req.diagnostics,
            conservative=(mode != "default"),
        ),
        system_prompt_v2=sys_v2,
        user_prompt_v2=user_v2,
        plan_v2=plan_v2,
        expanded_prompt_v2=exp_v2,
        processing_ms=elapsed,
        request_id=rid,
        heuristic_version=HEURISTIC_VERSION,
        heuristic2_version=(HEURISTIC2_VERSION if ir2 else None),
        trace=trace_lines,
        critique=critique_result,
    )


@router.post("/compile/fast", response_model=CompileResponse)
async def compile_fast(
    req: CompileRequest,
    request: Request,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    start = time.time()
    compiler = _get_compiler()

    try:
        mode = resolve_mode(req.mode, request)
        cache_key = (req.text, mode)
        cache_hit = cache_key in compiler.cache
        fallback_reason = None
        if cache_key in compiler.cache:
            res = compiler.cache[cache_key]
        else:
            try:
                res = await anyio.to_thread.run_sync(
                    functools.partial(compiler.worker.process, req.text, mode=mode)
                )
            except Exception as exc:
                fallback_reason = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "compile_fast worker failed; falling back to local heuristics",
                    exc_info=True,
                    extra={"mode": mode, "text_length": len(req.text)},
                )
                res = None

        payload, used_fallback = _fast_compile_payload(req, res, mode, start, fallback_reason)
        if not cache_hit and not used_fallback:
            compiler.cache[cache_key] = res
        elif cache_hit and used_fallback:
            compiler.cache.pop(cache_key, None)
        return payload
    except Exception as exc:
        logger.exception("compile_fast failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/validate", response_model=QualityReport)
def validate_endpoint(
    req: ValidateRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    try:
        compiler = _get_compiler()
        report = compiler.worker.analyze_prompt(req.text)

        from app.heuristics.handlers.safety import SafetyHandler

        safety = SafetyHandler()
        pii = safety._scan_pii(req.text)
        unsafe = safety._scan_unsafe_content(req.text)
        guardrail = safety._check_guardrails(req.text)

        safety_issues = []
        if pii:
            safety_issues.extend([f"PII Detected: {entry['type']}" for entry in pii])
        if unsafe:
            safety_issues.extend([f"Unsafe Content: '{entry}'" for entry in unsafe])
        if guardrail and guardrail.severity != "info":
            safety_issues.append(f"Guardrail: {guardrail.message}")

        if safety_issues:
            report.weaknesses = safety_issues + report.weaknesses
            report.score = max(0, report.score - (len(safety_issues) * 10))
            report.category_scores["safety"] = max(0, 100 - (len(safety_issues) * 30))

        return report
    except Exception as exc:
        logger.exception("validate endpoint failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_endpoint(
    req: OptimizeRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    compiler = _get_compiler()

    try:
        worker_model = getattr(compiler.worker, "model", None)
        model = (
            req.model
            or (worker_model if isinstance(worker_model, str) else None)
            or DEFAULT_GROQ_MODEL
        )
        provider = (req.provider or "groq").strip().lower()
        raw_result, optimizer_call_usage = await anyio.to_thread.run_sync(
            functools.partial(
                compiler.worker.optimize_prompt,
                req.text,
                max_chars=req.max_chars,
                max_tokens=req.max_tokens,
            )
        )
        result = strip_wrapper_labels(raw_result)
        source_cost = estimate_prompt_cost(req.text, provider=provider, model=model)
        optimized_cost = estimate_prompt_cost(result, provider=provider, model=model)

        warnings = list(dict.fromkeys(source_cost.warnings + optimized_cost.warnings))

        result_language = detect_language(result)
        if (
            source_cost.source_language not in ("unknown", "")
            and result_language not in ("unknown", "")
            and result_language != source_cost.source_language
        ):
            warnings.append(
                f"Optimized output language differs from input "
                f"({source_cost.source_language} → {result_language}); review before using."
            )

        if optimized_cost.tokens > source_cost.tokens > 0:
            warnings.append(
                "Optimized output uses more tokens than the input; "
                "consider keeping the original."
            )

        english_variant = ""
        english_variant_tokens = 0
        english_variant_cost_usd = 0.0

        if source_cost.source_language != "en":
            warnings.append("Translation can change nuance; review before using.")
            try:
                english_variant, _ = await anyio.to_thread.run_sync(
                    functools.partial(
                        compiler.worker.optimize_prompt_english_variant,
                        req.text,
                        max_chars=req.max_chars,
                        max_tokens=req.max_tokens,
                    )
                )
            except Exception as exc:
                logger.debug("English optimizer variant skipped: %s", exc)
                english_variant = ""
                warnings.append(
                    "English compact suggestion unavailable; the secondary optimizer call failed."
                )

            english_variant = strip_wrapper_labels(english_variant)

            if english_variant:
                english_cost = estimate_prompt_cost(english_variant, provider=provider, model=model)
                english_variant_tokens = english_cost.tokens
                english_variant_cost_usd = english_cost.estimated_cost_usd
                warnings = list(dict.fromkeys(warnings + english_cost.warnings))

        before_len = len(req.text)
        after_len = len(result)
        saved_percent = (
            round(((source_cost.tokens - optimized_cost.tokens) / source_cost.tokens) * 100, 1)
            if source_cost.tokens
            else 0.0
        )
        estimated_savings = round(
            source_cost.estimated_cost_usd - optimized_cost.estimated_cost_usd, 10
        )

        return OptimizeResponse(
            text=result,
            before_chars=before_len,
            after_chars=after_len,
            before_tokens=source_cost.tokens,
            after_tokens=optimized_cost.tokens,
            saved_percent=saved_percent,
            passes=1,
            met_max_chars=req.max_chars is None or after_len <= req.max_chars,
            met_max_tokens=req.max_tokens is None or optimized_cost.tokens <= req.max_tokens,
            met_budget=(req.max_chars is None or after_len <= req.max_chars)
            and (req.max_tokens is None or optimized_cost.tokens <= req.max_tokens),
            changed=(result != req.text),
            provider=provider,
            model=model,
            source_language=source_cost.source_language,
            tokenizer_method=source_cost.tokenizer_method,
            estimated_input_cost_usd=source_cost.estimated_cost_usd,
            estimated_output_cost_usd=optimized_cost.estimated_cost_usd,
            estimated_savings_usd=estimated_savings,
            english_variant=english_variant,
            english_variant_tokens=english_variant_tokens,
            english_variant_cost_usd=english_variant_cost_usd,
            warnings=warnings,
            optimizer_call_usage=optimizer_call_usage,
        )
    except Exception as exc:
        logger.exception("optimize endpoint failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
