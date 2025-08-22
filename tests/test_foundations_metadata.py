from app.compiler import compile_text


def test_temporal_and_quantities_present_when_triggered():
    ir = compile_text("teach me docker in 15 minutes this month with 3 examples")
    md = ir.metadata
    # temporal flags should capture relative time phrase
    assert any('month' in f.lower() for f in (md.get('temporal_flags') or []))
    # quantities should include time unit for 15 minutes
    assert any(q.get('value') == '15' and q.get('unit') in {'m','min','minutes'} for q in (md.get('quantities') or []))


def test_constraint_origins_mapping():
    ir = compile_text("teach me binary search in 10 minutes beginner level")
    origins = ir.metadata.get('constraint_origins') or {}
    assert origins, "constraint_origins should be present"
    # At least one teaching-origin constraint exists
    assert any(src.startswith('teaching') for src in origins.values())
