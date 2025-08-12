from app.compiler import compile_text
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan


def test_emitters_non_empty():
    ir = compile_text("Explain API design principles in detail")
    assert emit_system_prompt(ir)
    assert emit_user_prompt(ir)
    assert emit_plan(ir)
