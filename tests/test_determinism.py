from app.compiler import compile_text

def test_determinism():
    txt = "Explain API design principles in detail"
    ir1 = compile_text(txt)
    ir2 = compile_text(txt)
    assert ir1.dict() == ir2.dict()
