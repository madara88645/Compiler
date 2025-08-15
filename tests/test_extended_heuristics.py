from app.compiler import compile_text


def test_risk_flag_financial():
    ir = compile_text("analyze stock market investment strategy optimize performance")
    assert 'financial' in ir.metadata.get('risk_flags', [])
    assert any('general information' in c.lower() for c in ir.constraints)


def test_entities_and_complexity():
    ir = compile_text("Compare Kubernetes vs Docker orchestration in enterprise ISO 27001 context")
    ents = ir.metadata.get('entities', [])
    assert any(e in ents for e in ['Kubernetes','Docker'])
    assert ir.metadata.get('complexity') in {'low','medium','high'}


def test_ambiguous_terms_and_clarify():
    ir = compile_text("Improve scalable efficient system design")
    amb = ir.metadata.get('ambiguous_terms', [])
    assert 'improve' in amb or 'scalable' in amb or 'efficient' in amb
    qs = ir.metadata.get('clarify_questions', [])
    assert qs


def test_code_request_constraint():
    ir = compile_text("Provide Python code snippet for binary search")
    assert ir.metadata.get('code_request') is True
    assert any('inline comments' in c.lower() or 'yorum' in c.lower() for c in ir.constraints)
