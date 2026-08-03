from app.compiler import compile_text
from app.emitters import emit_system_prompt
from app.heuristics import detect_coding_context


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


def test_api_mention_does_not_force_developer_persona():
    """Test #701: lone 'api' token from 'REST API' or 'API keys' should not force developer persona."""
    # Educational/explanation requests with "REST API" or "API keys" should get assistant/teacher, not developer
    ir1 = compile_text("Explain REST API authentication methods")
    assert ir1.persona in {
        "assistant",
        "teacher",
    }, f"Expected assistant or teacher, got {ir1.persona}"

    ir2 = compile_text("What are API keys and how do they work?")
    assert ir2.persona in {
        "assistant",
        "teacher",
    }, f"Expected assistant or teacher, got {ir2.persona}"

    ir3 = compile_text("Teach me about REST API design principles")
    # This one might be teacher because of "teach me"
    assert ir3.persona in {
        "assistant",
        "teacher",
    }, f"Expected assistant or teacher, got {ir3.persona}"

    # But requests with stronger coding context should still get developer
    ir4 = compile_text("Build an API endpoint for user authentication")
    assert ir4.persona in {
        "developer",
        "assistant",
    }, f"Expected developer or assistant, got {ir4.persona}"

    ir5 = compile_text("Implement a REST API with Python Flask")
    assert ir5.persona in {
        "developer",
        "assistant",
    }, f"Expected developer or assistant, got {ir5.persona}"


def test_detect_coding_context_matches_strong_api_build_request():
    assert detect_coding_context("Build an API endpoint for user authentication") is True


def test_detect_coding_context_matches_react_debug_request():
    assert detect_coding_context(
        "My React app re-renders too much, help me fix the performance"
    ) is True


def test_detect_coding_context_keeps_api_explanations_non_coding():
    assert detect_coding_context("Explain REST API authentication methods") is False


def test_detect_coding_context_keeps_teaching_api_design_non_coding():
    assert detect_coding_context("Teach me about REST API design principles") is False


def test_detect_coding_context_keeps_browser_bug_report_separate():
    assert detect_coding_context("The download button is broken in Safari; help me fix it") is False


def test_strong_api_build_request_gets_coding_role_and_constraints():
    ir = compile_text("Build an API endpoint for user authentication")

    assert ir.persona == "developer"
    assert ir.role != "Helpful generative AI assistant"
    assert "coding assistant" in ir.role.lower()
    joined = " | ".join(ir.constraints).lower()
    assert "runnable" in joined
