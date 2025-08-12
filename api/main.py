from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel
from app.compiler import compile_text, optimize_ir
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan, emit_expanded_prompt

app = FastAPI(title="Prompt Compiler API")

class CompileRequest(BaseModel):
    text: str

class CompileResponse(BaseModel):
    ir: dict
    system_prompt: str
    user_prompt: str
    plan: str
    expanded_prompt: str

@app.get('/health')
async def health():
    return {"status": "ok"}

@app.post('/compile', response_model=CompileResponse)
async def compile_endpoint(req: CompileRequest):
    ir = optimize_ir(compile_text(req.text))
    return CompileResponse(
        ir=ir.dict(),
        system_prompt=emit_system_prompt(ir),
        user_prompt=emit_user_prompt(ir),
    plan=emit_plan(ir),
    expanded_prompt=emit_expanded_prompt(ir)
    )
