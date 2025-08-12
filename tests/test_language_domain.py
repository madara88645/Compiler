from app.compiler import compile_text

def test_language_tr():
    ir = compile_text("elon musk kimdir ve yapay zeka ile şu an ne yapıyor?")
    assert ir.language == 'tr'


def test_domain_ai():
    ir = compile_text("machine learning transformer model embedding")
    assert ir.domain in {'ai/ml','ai/nlp','general'}
    assert isinstance(ir.metadata.get('detected_domain_evidence'), list)
