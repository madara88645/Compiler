from app.heuristics.handlers.teaching import TeachingHandler
from app.models import IR
from app.models_v2 import IRv2
from app.compiler import compile_text_v2


def test_teaching_handler_direct_append():
    """Assert that TeachingHandler successfully appends 'teaching' to ir_v2.intents when ir_v1.persona is 'teacher'."""
    handler = TeachingHandler()

    ir_v1 = IR(
        language="en",
        persona="teacher",
        role="Teacher",
        domain="general",
        output_format="markdown",
        length_hint="medium",
    )
    ir_v2 = IRv2(
        language="en",
        persona="teacher",
        role="Teacher",
        domain="general",
        intents=[],
        output_format="markdown",
        length_hint="medium",
    )

    handler.handle(ir_v2, ir_v1)
    assert "teaching" in ir_v2.intents


def test_teaching_handler_direct_no_append_non_teacher():
    """Assert that TeachingHandler does not append 'teaching' to ir_v2.intents when ir_v1.persona is not 'teacher'."""
    handler = TeachingHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        output_format="markdown",
        length_hint="medium",
    )
    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        intents=[],
        output_format="markdown",
        length_hint="medium",
    )

    handler.handle(ir_v2, ir_v1)
    assert "teaching" not in ir_v2.intents


def test_teaching_persona_compiler_en():
    """Verify compile_text_v2 behaves correctly when compiler compiles prompts with teacher personas (English)."""
    ir = compile_text_v2("teach me binary search with examples")
    assert ir.persona == "teacher"
    assert "teaching" in ir.intents


def test_teaching_persona_compiler_tr():
    """Verify compile_text_v2 behaves correctly when compiler compiles prompts with teacher personas (Turkish)."""
    ir = compile_text_v2("bana grafik veri yapısını öğret, örneklerle anlat")
    assert ir.persona == "teacher"
    assert "teaching" in ir.intents


def test_teaching_persona_compiler_non_teaching():
    """Verify compile_text_v2 behaves correctly when compiling non-teacher prompts."""
    ir = compile_text_v2("write a python script to parse logs")
    assert ir.persona != "teacher"
    assert "teaching" not in ir.intents
