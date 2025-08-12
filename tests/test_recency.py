from app.compiler import compile_text

def test_recency_tool_and_constraint():
    ir = compile_text("elon musk kimdir ve yapay zeka ile şu an ne yapıyor?")
    assert 'web' in ir.tools
    assert any('Güncel bilgi' in c for c in ir.constraints)
