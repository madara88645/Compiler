from app.compiler import compile_text

def test_language_tr():
    ir = compile_text("elon musk kimdir ve yapay zeka ile şu an ne yapıyor?")
    assert ir.language == 'tr'


def test_domain_ai():
    ir = compile_text("machine learning transformer model embedding")
    assert ir.domain in {'ai/ml','ai/nlp','general'}
    assert isinstance(ir.metadata.get('detected_domain_evidence'), list)
    # domain candidates should include selected domain
    cands = ir.metadata.get('domain_candidates') or []
    if ir.domain != 'general':
        assert ir.domain in cands

def test_pii_detection_email_phone():
    ir = compile_text("Please review this contact: john.doe@example.com and phone +1 212-555-1234 for context")
    pii = ir.metadata.get('pii_flags') or []
    assert 'email' in pii and 'phone' in pii
    # Constraint should reflect privacy guidance
    assert any('privacy' in c.lower() or 'gizli' in c.lower() for c in ir.constraints)
