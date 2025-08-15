from app.compiler import compile_text
from app.emitters import emit_expanded_prompt


def test_expanded_without_diagnostics():
    ir = compile_text("Analyze stock market investment strategy and optimize performance")
    ep = emit_expanded_prompt(ir)
    assert "Diagnostics:" not in ep


def test_expanded_with_diagnostics():
    ir = compile_text("Analyze stock market investment strategy and optimize performance")
    ep = emit_expanded_prompt(ir, diagnostics=True)
    assert "Diagnostics:" in ep
    assert "Risk Flags:" in ep or "Ambiguous Terms:" in ep
