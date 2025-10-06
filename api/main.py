from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from app.compiler import HEURISTIC_VERSION, HEURISTIC2_VERSION
from app.compiler import compile_text, compile_text_v2, optimize_ir, generate_trace
import time
import uuid
from app import get_build_info
from app.emitters import (
    emit_system_prompt,
    emit_user_prompt,
    emit_plan,
    emit_expanded_prompt,
    emit_system_prompt_v2,
    emit_user_prompt_v2,
    emit_plan_v2,
    emit_expanded_prompt_v2,
)
from app.rag.simple_index import (
    ingest_paths,
    search as rag_search,
    search_embed as rag_search_embed,
    search_hybrid as rag_search_hybrid,
    pack as rag_pack_ctx,
    stats as rag_stats,
    prune as rag_prune,
)
from app.validator import validate_prompt
from app.analytics import AnalyticsManager, create_record_from_ir
from typing import List, Optional
from pydantic import Field

app = FastAPI(title="Prompt Compiler API")


class CompileRequest(BaseModel):
    text: str
    diagnostics: bool = False
    trace: bool = False
    v2: bool = True
    render_v2_prompts: bool = False


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


class RagIngestRequest(BaseModel):
    paths: List[str]
    exts: Optional[List[str]] = Field(
        default=None, description="Extensions like .txt .md (default: .txt .md .py)"
    )
    db_path: Optional[str] = None
    embed: bool = Field(
        default=False, description="If true, compute/store tiny deterministic embeddings"
    )
    embed_dim: int = Field(default=64, description="Embedding dimension (when embed=true)")


class RagIngestResponse(BaseModel):
    ingested_docs: int
    total_chunks: int
    elapsed_ms: int


class RagQueryRequest(BaseModel):
    query: str
    k: int = 5
    db_path: Optional[str] = None
    method: str = Field(default="fts", description="Retrieval method: fts|embed|hybrid")
    embed_dim: int = Field(default=64, description="Embedding dimension (for method=embed|hybrid)")
    alpha: float = Field(default=0.5, description="Hybrid weighting factor (fts vs embed)")


class RagQueryResponse(BaseModel):
    results: List[dict]
    count: int


class RagStatsRequest(BaseModel):
    db_path: Optional[str] = None


class RagStatsResponse(BaseModel):
    docs: int
    chunks: int
    total_bytes: int
    avg_bytes: float
    largest: List[dict]


class RagPruneRequest(BaseModel):
    db_path: Optional[str] = None


class RagPruneResponse(BaseModel):
    removed_docs: int
    removed_chunks: int


# (imports consolidated above)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Alias commonly used by load balancers/monitors
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/version")
async def version():
    """Return running package version (for debugging / client caching)."""
    return get_build_info()


@app.post("/compile", response_model=CompileResponse)
async def compile_endpoint(req: CompileRequest):
    t0 = time.time()
    rid = uuid.uuid4().hex[:12]
    # Always produce v1 for backward compatibility; use v2 by default for clients
    ir = optimize_ir(compile_text(req.text))
    elapsed = int((time.time() - t0) * 1000)
    trace_lines = generate_trace(ir) if req.trace else None
    ir2 = compile_text_v2(req.text) if req.v2 else None
    # Optional: render prompts with IR v2 emitters
    sys_v2 = user_v2 = plan_v2 = exp_v2 = None
    if req.render_v2_prompts and ir2 is not None:
        sys_v2 = emit_system_prompt_v2(ir2)
        user_v2 = emit_user_prompt_v2(ir2)
        plan_v2 = emit_plan_v2(ir2)
        exp_v2 = emit_expanded_prompt_v2(ir2, diagnostics=req.diagnostics)
    return CompileResponse(
        ir=ir.model_dump(),
        ir_v2=(ir2.model_dump() if ir2 else None),
        system_prompt=emit_system_prompt(ir),
        user_prompt=emit_user_prompt(ir),
        plan=emit_plan(ir),
        expanded_prompt=emit_expanded_prompt(ir, diagnostics=req.diagnostics),
        system_prompt_v2=sys_v2,
        user_prompt_v2=user_v2,
        plan_v2=plan_v2,
        expanded_prompt_v2=exp_v2,
        processing_ms=elapsed,
        request_id=rid,
        heuristic_version=HEURISTIC_VERSION,
        heuristic2_version=(HEURISTIC2_VERSION if req.v2 else None),
        trace=trace_lines,
    )


@app.get("/schema")
async def schema_endpoint():
    path = Path("schema/ir.schema.json")
    return {"schema": path.read_text(encoding="utf-8")}


@app.get("/schema/ir_v1")
async def schema_ir_v1():
    """Return IR v1 JSON schema (same as /schema legacy)."""
    path = Path("schema/ir.schema.json")
    return {"schema": path.read_text(encoding="utf-8")}


@app.get("/schema/ir_v2")
async def schema_ir_v2():
    """Return IR v2 JSON schema."""
    path = Path("schema/ir_v2.schema.json")
    return {"schema": path.read_text(encoding="utf-8")}


INDEX_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <title>Prompt Compiler UI</title>
    <style>
        body { font-family: system-ui, Arial, sans-serif; margin: 1.5rem; line-height: 1.4; }
        textarea { width: 100%; min-height: 140px; font-family: monospace; padding: .75rem; }
        button { margin-right: .6rem; padding: .5rem .9rem; cursor: pointer; }
        .row { margin-top: .75rem; }
        .outputs { display: grid; grid-template-columns: repeat(auto-fit,minmax(300px,1fr)); gap: 1rem; margin-top: 1rem; }
        pre { background:#111; color:#eee; padding:.75rem; overflow:auto; max-height: 400px; }
        h3 { margin-top:1.2rem; }
        .badge { background:#444; color:#fff; padding:2px 6px; border-radius:4px; font-size:.75rem; }
        .flex { display:flex; align-items:center; gap:.5rem; }
    </style>
</head>
<body>
    <h1>Prompt Compiler</h1>
    <p>Enter a natural language prompt and generate structured prompts & IR.</p>
    <textarea id=\"prompt\" placeholder=\"e.g. teach me gradient descent in 15 minutes at intermediate level\"></textarea>
    <div class=\"flex\">
        <label><input type=\"checkbox\" id=\"diagnostics\"/> diagnostics</label>
    </div>
    <div class=\"row\">
        <button id=\"btnGen\">Generate</button>
        <button id=\"btnSchema\">Show JSON Schema</button>
        <button id=\"btnClear\">Clear Outputs</button>
    <button id=\"btnCopyAll\">Copy All</button>
    <button id=\"btnExportIR\">Export IR JSON</button>
    </div>
    <div id=\"status\"></div>
    <div class=\"outputs\">
        <div><h3>System Prompt</h3><pre id=\"system\"></pre></div>
        <div><h3>User Prompt</h3><pre id=\"user\"></pre></div>
        <div><h3>Plan</h3><pre id=\"plan\"></pre></div>
        <div><h3>Expanded Prompt <span class=\"badge\" id=\"diagBadge\" style=\"display:none\">diagnostics</span></h3><pre id=\"expanded\"></pre></div>
        <div style=\"grid-column: 1 / -1;\"><h3>IR JSON</h3><pre id=\"ir\"></pre></div>
        <div style=\"grid-column: 1 / -1;\"><h3>JSON Schema</h3><pre id=\"schema\"></pre></div>
    </div>
    <script>
        const qs = id => document.getElementById(id);
        qs('btnGen').onclick = async () => {
            const text = qs('prompt').value.trim();
            if(!text){ alert('Enter prompt'); return; }
            qs('status').textContent = 'Generating...';
            qs('schema').textContent='';
            const diagnostics = qs('diagnostics').checked;
            try {
                const res = await fetch('/compile', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({text, diagnostics})
                });
                if(!res.ok){ throw new Error('HTTP '+res.status); }
                const data = await res.json();
                qs('system').textContent = data.system_prompt;
                qs('user').textContent = data.user_prompt;
                qs('plan').textContent = data.plan;
                qs('expanded').textContent = data.expanded_prompt;
                qs('ir').textContent = JSON.stringify(data.ir, null, 2);
                qs('diagBadge').style.display = diagnostics ? 'inline-block' : 'none';
                qs('status').textContent = 'Done';
            } catch(e){
                qs('status').textContent = 'Error: '+ e.message;
            }
        };
        qs('btnSchema').onclick = async () => {
            qs('status').textContent = 'Loading schema...';
            try {
                const r = await fetch('/schema');
                const js = await r.json();
                qs('schema').textContent = js.schema;
                qs('status').textContent = 'Schema loaded';
            } catch(e){ qs('status').textContent = 'Schema error: '+e.message; }
        };
        qs('btnClear').onclick = () => {
            ['system','user','plan','expanded','ir','schema','status'].forEach(id=>qs(id).textContent='');
        };
                qs('btnCopyAll').onclick = () => {
                        const parts = [];
                        const push = (title, txt) => { if(txt) parts.push(`# ${title}\n\n${txt}`) };
                        push('System Prompt', qs('system').textContent.trim());
                        push('User Prompt', qs('user').textContent.trim());
                        push('Plan', qs('plan').textContent.trim());
                        push('Expanded Prompt', qs('expanded').textContent.trim());
                        if(!parts.length){ return; }
                        const blob = new Blob([parts.join('\n\n')], {type:'text/plain'});
                        navigator.clipboard.writeText(parts.join('\n\n')).then(()=>{
                            qs('status').textContent = 'Copied all outputs';
                        }).catch(()=>{
                            qs('status').textContent = 'Copy failed';
                        });
                };
                qs('btnExportIR').onclick = () => {
                        const data = qs('ir').textContent.trim();
                        if(!data){ return; }
                        const blob = new Blob([data + '\n'], {type: 'application/json'});
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob);
                        a.download = 'ir.json';
                        a.click();
                        URL.revokeObjectURL(a.href);
                };
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root_page():
    return HTMLResponse(INDEX_HTML)


@app.post("/rag/ingest", response_model=RagIngestResponse)
async def rag_ingest(req: RagIngestRequest):
    docs, chunks, secs = ingest_paths(
        req.paths,
        db_path=req.db_path,
        exts=req.exts,
        embed=req.embed,
        embed_dim=req.embed_dim,
    )
    return RagIngestResponse(ingested_docs=docs, total_chunks=chunks, elapsed_ms=int(secs * 1000))


@app.post("/rag/query", response_model=RagQueryResponse)
async def rag_query(req: RagQueryRequest):
    method = (req.method or "fts").lower()
    if method not in {"fts", "embed", "hybrid"}:
        method = "fts"
    if method == "embed":
        res = rag_search_embed(req.query, k=req.k, db_path=req.db_path, embed_dim=req.embed_dim)
    elif method == "hybrid":
        res = rag_search_hybrid(
            req.query,
            k=req.k,
            db_path=req.db_path,
            embed_dim=req.embed_dim,
            alpha=req.alpha,
        )
    else:
        res = rag_search(req.query, k=req.k, db_path=req.db_path)
    return RagQueryResponse(results=res, count=len(res))


class RagPackRequest(BaseModel):
    query: str
    k: int = Field(default=8, description="Top-K to retrieve before packing")
    max_chars: int = Field(default=4000, description="Character budget for packed context")
    max_tokens: Optional[int] = Field(
        default=None, description="Approx token budget; overrides chars when set"
    )
    token_ratio: float = Field(default=4.0, description="Chars per token heuristic (default 4.0)")
    method: str = Field(default="hybrid", description="Retrieval method fts|embed|hybrid")
    embed_dim: int = Field(default=64, description="Embedding dimension (embed/hybrid)")
    alpha: float = Field(default=0.5, description="Hybrid weighting factor")
    db_path: Optional[str] = None


class RagPackResponse(BaseModel):
    packed: str
    included: List[dict]
    chars: int
    tokens: int | None = None
    query: str
    budget: dict | None = None


@app.post("/rag/pack", response_model=RagPackResponse)
async def rag_pack_endpoint(req: RagPackRequest):
    method = (req.method or "hybrid").lower()
    if method not in {"fts", "embed", "hybrid"}:
        method = "hybrid"
    if method == "embed":
        res = rag_search_embed(req.query, k=req.k, db_path=req.db_path, embed_dim=req.embed_dim)
    elif method == "hybrid":
        res = rag_search_hybrid(
            req.query,
            k=req.k,
            db_path=req.db_path,
            embed_dim=req.embed_dim,
            alpha=req.alpha,
        )
    else:
        res = rag_search(req.query, k=req.k, db_path=req.db_path)
    packed = rag_pack_ctx(
        req.query,
        res,
        max_chars=req.max_chars,
        max_tokens=req.max_tokens,
        token_chars=req.token_ratio,
    )
    return RagPackResponse(**packed)


@app.post("/rag/stats", response_model=RagStatsResponse)
async def rag_stats_endpoint(req: RagStatsRequest):
    s = rag_stats(db_path=req.db_path)
    return RagStatsResponse(**s)


@app.post("/rag/prune", response_model=RagPruneResponse)
async def rag_prune_endpoint(req: RagPruneRequest):
    r = rag_prune(db_path=req.db_path)
    return RagPruneResponse(**r)


# Validation endpoint
class ValidateRequest(BaseModel):
    text: str
    include_suggestions: bool = Field(default=True, description="Include improvement suggestions")
    include_strengths: bool = Field(default=True, description="Include identified strengths")


class ValidateResponse(BaseModel):
    score: dict
    issues: List[dict]
    strengths: List[str]
    summary: dict


@app.post("/validate", response_model=ValidateResponse)
async def validate_endpoint(req: ValidateRequest):
    """Validate a prompt and return quality score with suggestions.

    Returns:
        - score: Quality breakdown (total, clarity, specificity, completeness, consistency)
        - issues: List of validation issues with suggestions
        - strengths: Identified strong points
        - summary: Counts by severity (errors, warnings, info)
    """
    # Compile to IR v2
    ir2 = compile_text_v2(req.text)

    # Validate
    result = validate_prompt(ir2, original_text=req.text)

    # Convert to response format
    response_dict = result.to_dict()

    # Filter based on request options
    if not req.include_suggestions:
        for issue in response_dict["issues"]:
            issue.pop("suggestion", None)

    if not req.include_strengths:
        response_dict["strengths"] = []

    return ValidateResponse(**response_dict)


# -------------------------
# Auto-Fix
# -------------------------


class AutoFixRequest(BaseModel):
    text: str
    max_fixes: int = Field(default=5, description="Maximum number of fixes to apply")
    target_score: float = Field(
        default=75.0, ge=0, le=100, description="Stop when score reaches this threshold"
    )


class FixDetail(BaseModel):
    type: str
    description: str
    confidence: float


class AutoFixResponse(BaseModel):
    original_text: str
    fixed_text: str
    original_score: float
    fixed_score: float
    improvement: float
    fixes_applied: List[FixDetail]
    remaining_issues: int


@app.post("/fix", response_model=AutoFixResponse)
async def fix_endpoint(req: AutoFixRequest):
    """Automatically fix prompt based on validation issues.

    Returns:
        - original_text: Input prompt
        - fixed_text: Improved prompt
        - original_score: Score before fixes
        - fixed_score: Score after fixes
        - improvement: Score delta
        - fixes_applied: List of applied fixes
        - remaining_issues: Number of unresolved issues
    """
    from app.autofix import auto_fix_prompt

    result = auto_fix_prompt(req.text, max_fixes=req.max_fixes, min_score_target=req.target_score)

    return AutoFixResponse(
        original_text=result.original_text,
        fixed_text=result.fixed_text,
        original_score=round(result.original_score, 1),
        fixed_score=round(result.fixed_score, 1),
        improvement=round(result.improvement, 1),
        fixes_applied=[
            FixDetail(
                type=fix.fix_type,
                description=fix.description,
                confidence=round(fix.confidence, 2),
            )
            for fix in result.fixes_applied
        ],
        remaining_issues=result.remaining_issues,
    )


# ===== Compare Endpoint =====


class CompareRequest(BaseModel):
    """Request model for prompt comparison"""

    prompt_a: str = Field(..., description="First prompt text")
    prompt_b: str = Field(..., description="Second prompt text")
    label_a: str = Field("Prompt A", description="Label for first prompt")
    label_b: str = Field("Prompt B", description="Label for second prompt")


class CompareResponse(BaseModel):
    """Response model for prompt comparison"""

    prompt_a: str
    prompt_b: str
    validation_a: dict
    validation_b: dict
    ir_diff: str
    ir_changes: List[dict]
    score_difference: float
    better_prompt: Optional[str]
    recommendation: str
    category_comparison: dict


@app.post("/compare", response_model=CompareResponse)
async def compare_endpoint(req: CompareRequest):
    """Compare two prompts side by side.

    Returns:
        - prompt_a, prompt_b: Input prompts
        - validation_a, validation_b: Validation results with scores and issues
        - ir_diff: Unified diff between IRs
        - ir_changes: List of significant changes (field, type, details)
        - score_difference: B - A score delta
        - better_prompt: "A", "B", or null if equal
        - recommendation: Text recommendation
        - category_comparison: Per-category score comparison
    """
    from app.compare import compare_prompts

    result = compare_prompts(req.prompt_a, req.prompt_b, req.label_a, req.label_b)

    return CompareResponse(
        prompt_a=result.prompt_a,
        prompt_b=result.prompt_b,
        validation_a={
            "score": round(result.validation_a.score, 1),
            "category_scores": {
                k: round(v, 1) for k, v in result.validation_a.category_scores.items()
            },
            "issues": [issue.to_dict() for issue in result.validation_a.issues],
            "strengths": result.validation_a.strengths,
        },
        validation_b={
            "score": round(result.validation_b.score, 1),
            "category_scores": {
                k: round(v, 1) for k, v in result.validation_b.category_scores.items()
            },
            "issues": [issue.to_dict() for issue in result.validation_b.issues],
            "strengths": result.validation_b.strengths,
        },
        ir_diff=result.ir_diff,
        ir_changes=result.ir_changes,
        score_difference=round(result.score_difference, 1),
        better_prompt=result.better_prompt,
        recommendation=result.recommendation,
        category_comparison={
            k: {
                "score_a": round(v["score_a"], 1),
                "score_b": round(v["score_b"], 1),
                "difference": round(v["difference"], 1),
                "better": v["better"],
                "issues_a_count": v["issues_a_count"],
                "issues_b_count": v["issues_b_count"],
            }
            for k, v in result.category_comparison.items()
        },
    )


# ============================================================================
# Analytics Endpoints
# ============================================================================


class AnalyticsRecordRequest(BaseModel):
    prompt_text: str
    run_validation: bool = True


class AnalyticsRecordResponse(BaseModel):
    record_id: int
    validation_score: float
    domain: str
    language: str
    issues_count: int


class AnalyticsSummaryRequest(BaseModel):
    days: int = 30
    domain: Optional[str] = None
    persona: Optional[str] = None


class AnalyticsSummaryResponse(BaseModel):
    total_prompts: int
    avg_score: float
    min_score: float
    max_score: float
    score_std: float
    top_domains: List[tuple]
    top_personas: List[tuple]
    top_intents: List[tuple]
    language_distribution: dict
    avg_issues: float
    avg_prompt_length: int
    improvement_rate: float
    most_improved_domain: Optional[str]


class AnalyticsTrendsRequest(BaseModel):
    days: int = 30


class AnalyticsTrendsResponse(BaseModel):
    trends: List[dict]


class AnalyticsDomainsRequest(BaseModel):
    days: int = 30


class AnalyticsDomainsResponse(BaseModel):
    domains: dict


class AnalyticsStatsResponse(BaseModel):
    total_records: int
    overall_avg_score: float
    first_record: Optional[str]
    last_record: Optional[str]
    database_path: str


@app.post("/analytics/record", response_model=AnalyticsRecordResponse)
async def analytics_record(req: AnalyticsRecordRequest):
    """
    Record a prompt compilation in analytics database
    """
    from app.compiler import compile_text_v2

    # Compile prompt
    ir = compile_text_v2(req.prompt_text)

    # Validate if requested
    validation_result = None
    if req.run_validation:
        validation_result = validate_prompt(ir, req.prompt_text)

    # Create record
    record = create_record_from_ir(req.prompt_text, ir.model_dump(), validation_result)

    # Save
    manager = AnalyticsManager()
    record_id = manager.record_prompt(record)

    return AnalyticsRecordResponse(
        record_id=record_id,
        validation_score=record.validation_score,
        domain=record.domain,
        language=record.language,
        issues_count=record.issues_count,
    )


@app.post("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(req: AnalyticsSummaryRequest):
    """
    Get analytics summary for a time period
    """
    manager = AnalyticsManager()
    summary = manager.get_summary(days=req.days, domain=req.domain, persona=req.persona)

    return AnalyticsSummaryResponse(
        total_prompts=summary.total_prompts,
        avg_score=summary.avg_score,
        min_score=summary.min_score,
        max_score=summary.max_score,
        score_std=summary.score_std,
        top_domains=summary.top_domains,
        top_personas=summary.top_personas,
        top_intents=summary.top_intents,
        language_distribution=summary.language_distribution,
        avg_issues=summary.avg_issues,
        avg_prompt_length=summary.avg_prompt_length,
        improvement_rate=summary.improvement_rate,
        most_improved_domain=summary.most_improved_domain,
    )


@app.post("/analytics/trends", response_model=AnalyticsTrendsResponse)
async def analytics_trends(req: AnalyticsTrendsRequest):
    """
    Get score trends over time
    """
    manager = AnalyticsManager()
    trends = manager.get_score_trends(days=req.days)

    return AnalyticsTrendsResponse(trends=trends)


@app.post("/analytics/domains", response_model=AnalyticsDomainsResponse)
async def analytics_domains(req: AnalyticsDomainsRequest):
    """
    Get domain breakdown and statistics
    """
    manager = AnalyticsManager()
    domains = manager.get_domain_breakdown(days=req.days)

    return AnalyticsDomainsResponse(domains=domains)


@app.get("/analytics/stats", response_model=AnalyticsStatsResponse)
async def analytics_stats():
    """
    Get overall database statistics
    """
    manager = AnalyticsManager()
    stats = manager.get_stats()

    return AnalyticsStatsResponse(
        total_records=stats["total_records"],
        overall_avg_score=stats["overall_avg_score"],
        first_record=stats["first_record"],
        last_record=stats["last_record"],
        database_path=stats["database_path"],
    )
