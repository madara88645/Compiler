from app.compiler import compile_text_v2


def test_new_heuristics_integration():
    ir2 = compile_text_v2("Extract a list of items to JSON, make it short but very detailed.")
    constraints_v2_text = " ".join([c.text for c in ir2.constraints])

    assert "No conversational filler" in constraints_v2_text
    assert "CONFLICT DETECTED" in constraints_v2_text
