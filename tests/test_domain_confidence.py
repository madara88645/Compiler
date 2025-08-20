from app.compiler import compile_text


def test_domain_confidence_ratio_basic():
    text = "aws serverless lambda docker kubernetes python"
    ir = compile_text(text)
    md = ir.metadata
    # Expect cloud or software domain; evidence for both
    scores = md.get('domain_scores') or {}
    assert scores
    if ir.domain != 'general':
        assert ir.metadata.get('domain_confidence') is not None
        conf = ir.metadata['domain_confidence']
        assert 0 < conf <= 1
        # Primary domain count should be max
        primary_count = scores.get(ir.domain, 0)
        assert primary_count == max(scores.values())


def test_domain_confidence_none_for_general():
    ir = compile_text("explain something completely unrelated to tech or finance")
    if ir.domain == 'general':
        assert ir.metadata.get('domain_confidence') is None


def test_domain_confidence_ratio_single_domain_full():
    ir = compile_text("python python python api microservice docker")
    if ir.domain != 'general':
        # If only one domain present, confidence should be 1.0
        scores = ir.metadata.get('domain_scores') or {}
        if len(scores) == 1:
            assert abs(ir.metadata.get('domain_confidence') - 1.0) < 1e-9
