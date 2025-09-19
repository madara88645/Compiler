from app.compiler import compile_text
from app.emitters import emit_expanded_prompt


def test_expanded_prompt_contains_input_and_example():
    txt = "arkadaşıma hediye öner futbol sever"
    ir = compile_text(txt)
    ep = emit_expanded_prompt(ir)
    assert "Genişletilmiş İstem" in ep or "Expanded Prompt" in ep
    assert "Input" in ep or "Girdi" in ep
    assert ("Örnek çıktı formatı" in ep) or ("Example output format" in ep)
