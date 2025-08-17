from app.compiler import compile_text

def test_half_hour_tr():
    ir = compile_text('yarım saat içinde bana temel sql öğret')
    assert ir.inputs.get('duration') == '30m'

def test_half_hour_en():
    ir = compile_text('half hour tutorial about docker basics')
    assert ir.inputs.get('duration') == '30m'

def test_half_an_hour_en():
    ir = compile_text('half an hour guide to python lists')
    assert ir.inputs.get('duration') == '30m'
