from __future__ import annotations
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.compiler import HEURISTIC_VERSION, HEURISTIC2_VERSION
from app.llm_engine.schemas import QualityReport

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
from typing import List, Optional
from pydantic import Field
from api.auth import verify_api_key, APIKey
from fastapi import Depends

# Global Hybrid Compiler Instance (Lazy Load)
hybrid_compiler = None

app = FastAPI(title="Prompt Compiler API")


app.add_middleware(
    CORSMiddleware,
    # Allow specific origins from env (comma separated) or default to *
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---
from app.routers.benchmark import router as benchmark_router  # noqa: E402

app.include_router(benchmark_router)


# Define endpoint after models are defined


@app.on_event("startup")
async def startup_event():
    global hybrid_compiler
    from app.llm_engine.hybrid import HybridCompiler

    hybrid_compiler = HybridCompiler()
    print(f"[BACKEND] HybridCompiler initialized (v{get_build_info()['version']})")

    # --- SaaS Mode: Wait for user to ingest via API ---
    # background_ingest removed to prevent indexing the compiler's own source code.


class CompileRequest(BaseModel):
    text: str
    diagnostics: bool = False
    trace: bool = False
    v2: bool = True
    render_v2_prompts: bool = False
    record_analytics: bool = False
    user_level: str = "intermediate"
    task_type: str = "general"
    tags: Optional[List[str]] = None


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
    heuristic2_version: str | None = None
    trace: list[str] | None = None
    critique: dict | None = None


@app.post("/compile/fast", response_model=CompileResponse)
async def compile_fast(
    req: CompileRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    """
    Fast optimization endpoint.
    Bypasses RAG and heavy context retrieval.
    Secured by API Key and Rate Limited.
    """
    import time

    start = time.time()

    # Direct Worker call (Bypass HybridCompiler RAG logic)
    # We assume hybrid_compiler is initialized
    if hybrid_compiler is None:
        raise HTTPException(status_code=503, detail="Compiler not initialized")

    try:
        # 1. Check Cache (Optional, but good for speed)
        # Note: WorkerResponse handles caching internally usually, but hybrid_compiler has a cache
        if req.text in hybrid_compiler.cache:
            res = hybrid_compiler.cache[req.text]
        else:
            # 2. Direct LLM Call
            # We skip context_strategist.process(req.text)
            res = hybrid_compiler.worker.process(req.text)
            hybrid_compiler.cache[req.text] = res

        return {
            "ir": res.ir.model_dump(),
            # IRv2 mapping if available
            "ir_v2": res.ir.model_dump(),
            "system_prompt": res.system_prompt,
            "user_prompt": res.user_prompt,
            "plan": res.plan,
            "expanded_prompt": res.optimized_content,
            "system_prompt_v2": res.system_prompt,  # Fill v2 fields
            "user_prompt_v2": res.user_prompt,
            "plan_v2": res.plan,
            "expanded_prompt_v2": res.optimized_content,
            "processing_ms": int((time.time() - start) * 1000),
            "request_id": "fast_" + str(int(time.time())),
            "heuristic_version": "v2-fast",
            "heuristic2_version": "v2-fast",
            "trace": [],
            "critique": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Skills Generator Endpoints
# ============================================================================


class SkillGenRequest(BaseModel):
    description: str = Field(..., description="Description of the skill to generate")


class SkillGenResponse(BaseModel):
    skill_definition: str


@app.post("/skills-generator/generate", response_model=SkillGenResponse)
async def generate_skill_endpoint(req: SkillGenRequest):
    """Generate a comprehensive AI Skill definition."""
    if hybrid_compiler is None:
        raise HTTPException(status_code=503, detail="Compiler not initialized")

    try:
        result = hybrid_compiler.generate_skill(req.description)
        return SkillGenResponse(skill_definition=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OptimizeRequest(BaseModel):
    text: str
    max_chars: Optional[int] = Field(
        default=None, description="Character budget (best-effort; the server will not truncate)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Approximate token budget (best-effort; the server will not truncate)",
    )
    token_ratio: float = Field(
        default=4.0, description="Chars per token heuristic (same convention as RAG)"
    )


class OptimizeResponse(BaseModel):
    text: str
    before_chars: int
    after_chars: int
    before_tokens: int
    after_tokens: int
    passes: int
    met_max_chars: bool
    met_max_tokens: bool
    met_budget: bool
    changed: bool


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
def compile_endpoint(req: CompileRequest):
    """Compile a prompt using the Hybrid Compiler Engine."""
    t0 = time.time()
    rid = uuid.uuid4().hex[:12]

    # Always compute V1 heuristic IR for backward compatibility
    ir = optimize_ir(compile_text(req.text))
    trace_lines = generate_trace(ir) if req.trace else None

    # Always run V2 Heuristics (Logic, Structure, etc.) locally
    # this provides advanced features even in Offline Mode
    ir2 = compile_text_v2(req.text)

    sys_v2 = user_v2 = plan_v2 = exp_v2 = None

    if req.v2:
        # Online Mode: Use HybridCompiler (LLM)
        # hybrid_compiler.compile likely calls the LLM worker
        try:
            worker_res = hybrid_compiler.compile(req.text)
            # Merge LLM results into ir2 or replace?
            # HybridCompiler usually returns its own IR. Let's rely on it for Online.
            ir2 = worker_res.ir

            if worker_res.system_prompt:
                sys_v2 = worker_res.system_prompt
            if worker_res.user_prompt:
                user_v2 = worker_res.user_prompt
            if worker_res.plan:
                plan_v2 = worker_res.plan
            if worker_res.optimized_content:
                exp_v2 = worker_res.optimized_content
        except Exception as e:
            # Fallback to local V2 if LLM fails
            print(f"LLM Failed, falling back to local V2: {e}")
            pass
    else:
        # Offline Mode: Use local V2 Heuristics
        # We rely on the standard V2 emitters below to render IR2 results (including Schema/Diagnostics)
        pass

    # Optional: render prompts with IR v2 emitters (fallback if LLM didn't provide)
    if req.render_v2_prompts and ir2 is not None:
        sys_v2 = sys_v2 or emit_system_prompt_v2(ir2)
        user_v2 = user_v2 or emit_user_prompt_v2(ir2)
        plan_v2 = plan_v2 or emit_plan_v2(ir2)
        exp_v2 = exp_v2 or emit_expanded_prompt_v2(ir2, diagnostics=req.diagnostics)

    # -------------------------------------------------------------------------
    # NEW: Agent 7 - The Critic (System Prompt Review)
    # -------------------------------------------------------------------------
    critique_result = None
    if sys_v2:
        try:
            from app.optimizer.critic import CriticAgent

            critic = CriticAgent()

            # Prepare context string from IR metadata if available
            context_str = ""
            if ir2 and ir2.metadata.get("context_snippets"):
                snippets = ir2.metadata["context_snippets"]
                context_str = "\n\n".join(
                    [f"--- File: {s.get('path')} ---\n{s.get('snippet', '')}" for s in snippets]
                )

            critique_verdict = critic.critique(
                user_request=req.text, system_prompt=sys_v2, context=context_str
            )
            critique_result = critique_verdict.model_dump()

            # If rejected, we might want to log it or flag it
            if critique_verdict.verdict == "REJECT":
                print(f"[CRITIC] Detailed Feedback: {critique_verdict.feedback}")

        except Exception as e:
            print(f"[CRITIC] Failed to critique: {e}")
            pass
    # -------------------------------------------------------------------------

    elapsed = int((time.time() - t0) * 1000)

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
        heuristic2_version=(HEURISTIC2_VERSION if ir2 else None),
        trace=trace_lines,
        critique=critique_result,
    )


@app.post("/optimize", response_model=OptimizeResponse)
async def optimize_endpoint(req: OptimizeRequest):
    """Deterministically shorten prompt text using Worker LLM."""

    from app.text_utils import estimate_tokens

    # Use global hybrid compiler's worker
    global hybrid_compiler
    if hybrid_compiler is None:
        from app.llm_engine.hybrid import HybridCompiler

        hybrid_compiler = HybridCompiler()
    worker = hybrid_compiler.worker

    # Calculate initial stats
    before_chars = len(req.text)
    before_tokens = estimate_tokens(req.text)

    # Call Optimizer
    try:
        optimized = worker.optimize_prompt(
            req.text, max_tokens=req.max_tokens, max_chars=req.max_chars
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Calculate final stats
    after_chars = len(optimized)
    after_tokens = estimate_tokens(optimized)

    met_max_tokens = True
    if req.max_tokens and after_tokens > req.max_tokens:
        met_max_tokens = False

    met_max_chars = True
    if req.max_chars and after_chars > req.max_chars:
        met_max_chars = False

    return OptimizeResponse(
        text=optimized,
        before_chars=before_chars,
        after_chars=after_chars,
        before_tokens=before_tokens,
        after_tokens=after_tokens,
        passes=1,  # LLM does it in one pass usually
        met_max_chars=met_max_chars,
        met_max_tokens=met_max_tokens,
        met_budget=met_max_chars and met_max_tokens,
        changed=(optimized != req.text),
    )


@app.get("/schema")
async def schema_endpoint():
    from app.resources import get_ir_schema_text

    return {"schema": get_ir_schema_text(v2=False)}


@app.get("/schema/ir_v1")
async def schema_ir_v1():
    """Return IR v1 JSON schema (same as /schema legacy)."""
    from app.resources import get_ir_schema_text

    return {"schema": get_ir_schema_text(v2=False)}


@app.get("/schema/ir_v2")
async def schema_ir_v2():
    """Return IR v2 JSON schema."""
    from app.resources import get_ir_schema_text

    return {"schema": get_ir_schema_text(v2=True)}


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


# GET version for frontend ContextManager (fetchStats uses GET)
@app.get("/rag/stats", response_model=RagStatsResponse)
async def rag_stats_get():
    s = rag_stats()
    return RagStatsResponse(**s)


# --- SaaS Mode: Upload file content directly ---
class RagUploadRequest(BaseModel):
    filename: str = Field(..., description="Original filename (e.g. auth.py)")
    content: str = Field(..., description="Full text content of the file")
    force: bool = Field(default=False, description="Re-index even if already exists")


class RagUploadResponse(BaseModel):
    success: bool
    num_chunks: int
    message: str


@app.post("/rag/upload", response_model=RagUploadResponse)
def rag_upload_endpoint(req: RagUploadRequest):
    """Upload a single file's content for RAG indexing (SaaS mode)."""
    import tempfile
    import os
    from pathlib import Path
    from app.rag.simple_index import _connect, _init_schema, _chunk_text
    import re

    try:
        # Derive a safe suffix from the original filename extension
        raw_suffix = os.path.splitext(req.filename)[1]
        if raw_suffix and re.fullmatch(r"\.[A-Za-z0-9]+", raw_suffix):
            suffix = raw_suffix
        else:
            suffix = ".txt"

        # Derive a safe prefix from the original filename (used only for temp file naming)
        # Use only the basename and replace unsafe characters to avoid path injection
        base_name = os.path.basename(req.filename)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", base_name) or "file"
        # Optionally limit length to avoid overly long filenames
        safe_name = safe_name[:50]

        # Write content to a temp file so _insert_document can stat() it
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            prefix=f"rag_{safe_name}_",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(req.content)
            tmp_path = Path(tmp.name)

        # Index into the RAG database
        conn = _connect()
        _init_schema(conn)

        # Check if already indexed (by filename, not temp path)
        # We store the original filename as the "path" for display
        cur = conn.execute("SELECT id FROM docs WHERE path = ?", (req.filename,))
        existing = cur.fetchone()
        if existing and not req.force:
            os.unlink(tmp_path)
            return RagUploadResponse(
                success=True,
                num_chunks=0,
                message=f"{req.filename} already indexed. Use force=true to re-index.",
            )

        # Delete old entry if re-indexing
        if existing:
            doc_id = existing[0]
            conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            conn.execute("DELETE FROM docs WHERE id=?", (doc_id,))

        # Insert with original filename as path
        cur = conn.execute(
            """INSERT INTO docs(path, mtime, size) VALUES(?, ?, ?)
               RETURNING id""",
            (req.filename, os.path.getmtime(tmp_path), len(req.content)),
        )
        doc_id = cur.fetchone()[0]

        chunks = _chunk_text(req.content)
        for idx, chunk in enumerate(chunks):
            conn.execute(
                "INSERT INTO chunks(doc_id, chunk_index, content) VALUES(?, ?, ?)",
                (doc_id, idx, chunk),
            )

        conn.commit()
        conn.close()

        # Cleanup temp file
        os.unlink(tmp_path)

        return RagUploadResponse(
            success=True,
            num_chunks=len(chunks),
            message=f"Indexed {req.filename} ({len(chunks)} chunks)",
        )
    except Exception as e:
        return RagUploadResponse(success=False, num_chunks=0, message=str(e))


@app.post("/rag/prune", response_model=RagPruneResponse)
async def rag_prune_endpoint(req: RagPruneRequest):
    r = rag_prune(db_path=req.db_path)
    return RagPruneResponse(**r)


# Summarize Endpoint
class RagSummarizeRequest(BaseModel):
    text: str = Field(..., description="Document text to summarize")
    max_tokens: int = Field(default=500, description="Target max tokens for summary")


class RagSummarizeResponse(BaseModel):
    original_tokens: int
    summary_tokens: int
    summary: str
    compression_ratio: float


@app.post("/rag/summarize", response_model=RagSummarizeResponse)
async def rag_summarize_endpoint(req: RagSummarizeRequest):
    """Summarize a document using LLM compression."""
    from app.rag.summarizer import summarize_document, count_tokens_approx

    original_tokens = count_tokens_approx(req.text)

    try:
        summary = summarize_document(req.text, max_tokens=req.max_tokens)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

    summary_tokens = count_tokens_approx(summary)
    compression_ratio = (
        round(original_tokens / max(summary_tokens, 1), 2) if original_tokens > 0 else 1.0
    )

    return RagSummarizeResponse(
        original_tokens=original_tokens,
        summary_tokens=summary_tokens,
        summary=summary,
        compression_ratio=compression_ratio,
    )


class ValidateRequest(BaseModel):
    text: str
    include_suggestions: bool = Field(default=True, description="Include improvement suggestions")
    include_strengths: bool = Field(default=True, description="Include identified strengths")


@app.post("/validate", response_model=QualityReport)
def validate_endpoint(req: ValidateRequest):
    """Validate a prompt using Quality Coach."""
    try:
        # 1. Run LLM Analysis
        report = hybrid_compiler.worker.analyze_prompt(req.text)

        # 2. Run Offline Safety Checks
        from app.heuristics.handlers.safety import SafetyHandler

        safety = SafetyHandler()

        pii = safety._scan_pii(req.text)
        unsafe = safety._scan_unsafe_content(req.text)
        guardrail = safety._check_guardrails(req.text)

        safety_issues = []
        if pii:
            safety_issues.extend([f"PII Detected: {p['type']}" for p in pii])
        if unsafe:
            safety_issues.extend([f"Unsafe Content: '{u}'" for u in unsafe])
        if guardrail and guardrail.severity != "info":
            safety_issues.append(f"Guardrail: {guardrail.message}")

        if safety_issues:
            # Inject into report
            report.weaknesses = safety_issues + report.weaknesses
            # Penalty on score
            report.score = max(0, report.score - (len(safety_issues) * 10))
            # Add explicit safety category
            report.category_scores["safety"] = max(0, 100 - (len(safety_issues) * 30))

        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Auto-Fix
# -------------------------


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
# RAG / Context Endpoints
# ============================================================================


class IngestRequest(BaseModel):
    paths: List[str] = Field(..., description="List of file paths or directories to ingest")
    force: bool = False


class IngestResponse(BaseModel):
    num_files: int
    num_chunks: int
    errors: List[str]


@app.post("/rag/ingest", response_model=IngestResponse)
async def ingest_endpoint(req: IngestRequest):
    """Ingest files into the RAG index."""
    try:
        # Resolve paths relative to user home or current dir if needed
        # For security, we might want to restrict this, but for local tool it's fine.
        count, chunks, elapsed = ingest_paths(req.paths)
        errors = []  # ingest_paths no longer returns errors
        return IngestResponse(num_files=count, num_chunks=chunks, errors=errors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    method: str = "hybrid"  # keyword, vector, hybrid


class SearchResult(BaseModel):
    content: str
    source: str
    score: float


@app.post("/rag/search", response_model=List[SearchResult])
async def search_endpoint(req: SearchRequest):
    """Search the RAG index."""
    try:
        if req.method == "vector":
            results = rag_search_embed(req.query, k=req.limit)
        elif req.method == "keyword":
            results = rag_search(req.query, k=req.limit)
        else:
            results = rag_search_hybrid(req.query, k=req.limit)

        response = []
        for r in results:
            # Handle both dict (keyword/hybrid) and object (vector/other) results
            if isinstance(r, dict):
                content = r.get("snippet") or r.get("content") or ""
                source = r.get("path") or r.get("metadata", {}).get("source", "unknown")
                score = r.get("score") or r.get("hybrid_score") or 0.0
            else:
                # Assume object has attributes
                content = getattr(r, "content", "")
                source = getattr(r, "metadata", {}).get("source", "unknown")
                score = getattr(r, "score", 0.0)

            response.append(SearchResult(content=content, source=source, score=score))

        return response
    except Exception as e:
        print(f"RAG Search failed: {e}")
        return []


class FileUploadRequest(BaseModel):
    filename: str = Field(..., description="Name of the uploaded file")
    content: str = Field(..., description="File content as text")
    force: bool = False


class FileUploadResponse(BaseModel):
    success: bool
    num_chunks: int
    filename: str
    message: str


@app.post("/rag/upload", response_model=FileUploadResponse)
async def upload_file_endpoint(req: FileUploadRequest):
    """Upload a file directly (for drag & drop / paste).

    Accepts file content as text and indexes it into the RAG system.
    """
    import tempfile
    import os

    try:
        # Create a temporary file with the content
        # This allows us to reuse the existing ingest_paths logic
        temp_dir = tempfile.mkdtemp(prefix="rag_upload_")
        temp_path = os.path.join(temp_dir, req.filename)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(req.content)

        # Ingest the temporary file
        count, chunks, elapsed = ingest_paths([temp_path])

        # Clean up temp file
        try:
            os.remove(temp_path)
            os.rmdir(temp_dir)
        except OSError:
            pass

        if count == 0:
            return FileUploadResponse(
                success=False,
                num_chunks=0,
                filename=req.filename,
                message="Failed to index file",
            )

        return FileUploadResponse(
            success=True,
            num_chunks=chunks,
            filename=req.filename,
            message=f"Indexed {req.filename} ({chunks} chunks)",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/stats")
async def stats_endpoint():
    """Get RAG index statistics."""
    try:
        if rag_stats:
            return rag_stats()
        return {"error": "Stats function not available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/rag/debug_search")
async def debug_search_endpoint(query: str):
    """Debug endpoint to run raw SQL checks."""
    import sqlite3
    import os

    try:
        from app.rag.simple_index import DEFAULT_DB_PATH

        if not os.path.exists(DEFAULT_DB_PATH):
            return {"error": f"DB file not found at {DEFAULT_DB_PATH}"}

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        debug_info = {
            "db_path": DEFAULT_DB_PATH,
            "query": query,
            "fts_results": [],
            "like_results": [],
            "chunks_sample": [],
        }

        # 1. Check FTS
        try:
            cur = conn.execute("SELECT rowid, * FROM fts WHERE fts MATCH ? LIMIT 5", (f"{query}*",))
            debug_info["fts_results"] = [str(row) for row in cur.fetchall()]
        except Exception as e:
            debug_info["fts_error"] = str(e)

        # 2. Check LIKE
        try:
            cur = conn.execute(
                "SELECT id, content FROM chunks WHERE lower(content) LIKE lower(?) LIMIT 5",
                (f"%{query}%",),
            )
            debug_info["like_results"] = [str(row) for row in cur.fetchall()]
        except Exception as e:
            debug_info["like_error"] = str(e)

        # 3. Dump random chunks
        cur = conn.execute("SELECT id, content FROM chunks LIMIT 3")
        debug_info["chunks_sample"] = [f"{row[0]}: {row[1][:50]}..." for row in cur.fetchall()]

        conn.close()
        return debug_info

    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Analytics Endpoints
# ============================================================================


class AnalyticsRecordRequest(BaseModel):
    prompt_text: str
    run_validation: bool = True


# ============================================================================
# Agent Generator Endpoints
# ============================================================================


class AgentGenRequest(BaseModel):
    description: str = Field(..., description="Description of the agent to generate")
    multi_agent: bool = Field(
        default=False, description="Whether to decompose into multiple agents"
    )


class AgentGenResponse(BaseModel):
    system_prompt: str


@app.post("/agent-generator/generate", response_model=AgentGenResponse)
async def generate_agent_endpoint(req: AgentGenRequest):
    """Generate a comprehensive AI Agent system prompt."""
    if hybrid_compiler is None:
        raise HTTPException(status_code=503, detail="Compiler not initialized")

    try:
        result = hybrid_compiler.generate_agent(req.description, multi_agent=req.multi_agent)
        return AgentGenResponse(system_prompt=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
