from app.compiler import compile_text

def test_teaching_intent_tr():
    ir = compile_text("bana grafik veri yapısını öğret, örneklerle anlat")
    assert any("öğretici" in c or "pedagog" in c for c in [x.lower() for x in ir.constraints]) or ir.steps
    assert "friendly" in [x.lower() for x in ir.tone]
    assert any("kaynak" in c.lower() or "güvenilir" in c.lower() for c in ir.constraints)


def test_teaching_intent_en():
    ir = compile_text("teach me binary search with examples")
    assert any("pedagogical" in c or "progressive" in c for c in [x.lower() for x in ir.constraints]) or ir.steps
    assert "friendly" in [x.lower() for x in ir.tone]
    assert any("source" in c.lower() and "recommend" in c.lower() for c in ir.constraints)
