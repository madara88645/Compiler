from app.compiler import compile_text_v2


def test_irv2_debug_intent_on_live_debug():
    ir2 = compile_text_v2("Live debug this error and create an MRE in Python")
    assert "debug" in ir2.intents
    assert "code" in ir2.intents
