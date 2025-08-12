from app.compiler import compile_text


def test_tr_level_and_duration():
    ir = compile_text("bana 10 dakikada başlangıç seviyesinde binary search öğret")
    assert ir.inputs.get('duration') in {'10m','10min','10m'}
    assert ir.inputs.get('level') == 'beginner'
    assert any('Süre hedefi' in c for c in ir.constraints)


def test_en_level_and_duration():
    ir = compile_text("teach me gradient descent in 15 minutes at intermediate level")
    assert ir.inputs.get('duration') in {'15m','15min'}
    assert ir.inputs.get('level') == 'intermediate'
    assert any('Time-bound' in c for c in ir.constraints)
