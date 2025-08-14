from app.compiler import compile_text
from app.emitters import emit_system_prompt, emit_expanded_prompt


def test_system_prompt_contains_persona():
    ir = compile_text("teach me recursion tutorial")
    sp = emit_system_prompt(ir)
    assert "Persona:" in sp.splitlines()[0]


def test_expanded_prompt_context_persona():
    ir = compile_text("research and analyze recent literature on quantum computing")
    ep = emit_expanded_prompt(ir)
    assert "Persona:" in ep
