from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from app.compiler import compile_text, optimize_ir, HEURISTIC_VERSION
from app.compiler import compile_text_v2, HEURISTIC2_VERSION
import time, uuid
from app import get_version
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt

app = FastAPI(title="Prompt Compiler API")

class CompileRequest(BaseModel):
    text: str
    diagnostics: bool = False
    trace: bool = False
    v2: bool = False

class CompileResponse(BaseModel):
    ir: dict
    ir_v2: dict | None = None
    system_prompt: str
    user_prompt: str
    plan: str
    expanded_prompt: str
    processing_ms: int
    request_id: str
    heuristic_version: str
    heuristic2_version: str | None = None
    trace: list[str] | None = None
from app.compiler import compile_text, optimize_ir, HEURISTIC_VERSION, generate_trace

@app.get('/health')
async def health():
    return {"status": "ok"}

@app.get('/version')
async def version():
    """Return running package version (for debugging / client caching)."""
    return {"version": get_version()}

@app.post('/compile', response_model=CompileResponse)
async def compile_endpoint(req: CompileRequest):
    t0 = time.time()
    rid = uuid.uuid4().hex[:12]
    ir = optimize_ir(compile_text(req.text))
    elapsed = int((time.time() - t0)*1000)
    trace_lines = generate_trace(ir) if req.trace else None
    ir2 = compile_text_v2(req.text) if req.v2 else None
    return CompileResponse(
        ir=ir.dict(),
        ir_v2=(ir2.dict() if ir2 else None),
        system_prompt=emit_system_prompt(ir),
        user_prompt=emit_user_prompt(ir),
        plan=emit_plan(ir),
        expanded_prompt=emit_expanded_prompt(ir, diagnostics=req.diagnostics),
        processing_ms=elapsed,
        request_id=rid,
        heuristic_version=HEURISTIC_VERSION,
        heuristic2_version=(HEURISTIC2_VERSION if req.v2 else None),
        trace=trace_lines
    )


@app.get('/schema')
async def schema_endpoint():
        path = Path('schema/ir.schema.json')
        return {"schema": path.read_text(encoding='utf-8')}


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
    </script>
</body>
</html>"""

@app.get('/', response_class=HTMLResponse)
async def root_page():
        return HTMLResponse(INDEX_HTML)
