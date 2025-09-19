from app.compiler import compile_text
from app.emitters import emit_system_prompt


def test_developer_persona_on_code_request_en():
    ir = compile_text("Please implement a Python function to parse URLs and include tests")
    assert ir.persona in {"developer", "assistant"}
    if ir.persona == "developer":
        sp = emit_system_prompt(ir)
        assert "Persona:" in sp.splitlines()[0]
        assert "developer" in sp.lower()
        # coding constraints should be present
        joined = " | ".join(ir.constraints).lower()
        assert "runnable" in joined or "çalıştırılabilir" in joined


def test_developer_persona_on_code_terms_tr():
    ir = compile_text("Birlikte kodla: basit bir Python sınıfı yazalım ve test ekleyelim")
    assert ir.persona in {"developer", "assistant"}
    # ensure constraints reflect coding guidance
    j = " | ".join(ir.constraints).lower()
    assert "test" in j or "örnek" in j


def test_live_debug_en_constraints():
    ir = compile_text(
        "Live debug this traceback and help me reproduce with a minimal repro in Python"
    )
    assert ir.persona in {"developer", "assistant"}
    joined = " | ".join(ir.constraints).lower()
    assert "reproducible" in joined or "mre" in joined or "reproduce" in joined


def test_live_debug_tr_constraints():
    ir = compile_text(
        "Canlı debug: bu hata ayıklamada yığın izini analiz edip minimal örnek oluştur"
    )
    assert ir.persona in {"developer", "assistant"}
    j = " | ".join(ir.constraints).lower()
    assert "minimal" in j or "örnek" in j or "mre" in j
