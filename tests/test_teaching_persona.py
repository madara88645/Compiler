"""TeachingHandler unit tests and teacher persona integration."""

import pytest

from app.compiler import compile_text_v2
from app.heuristics.handlers.teaching import TeachingHandler
from app.models import IR
from app.models_v2 import IRv2


@pytest.fixture
def handler():
    return TeachingHandler()


def _ir(persona="assistant", metadata=None) -> IR:
    return IR(
        language="en",
        persona=persona,
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata=metadata or {},
    )


def _run(handler, persona="assistant", metadata=None):
    ir_v1 = _ir(persona=persona, metadata=metadata)
    ir_v2 = IRv2()
    handler.handle(ir_v2, ir_v1)
    return ir_v2


def test_teacher_persona_appends_teaching_intent(handler):
    ir_v2 = _run(handler, persona="teacher")
    assert ir_v2.intents == ["teaching"]


@pytest.mark.parametrize(
    "persona",
    ["assistant", "developer", "researcher", "coach", "mentor"],
)
def test_non_teacher_persona_does_not_append_teaching_intent(handler, persona):
    ir_v2 = _run(handler, persona=persona)
    assert "teaching" not in ir_v2.intents


def test_teacher_persona_does_not_block_other_intents(handler):
    ir_v1 = _ir(persona="teacher")
    ir_v2 = IRv2(intents=["explanation"])
    handler.handle(ir_v2, ir_v1)
    assert ir_v2.intents == ["explanation", "teaching"]


def test_compile_v2_teaching_prompt_sets_teaching_intent():
    ir_v2 = compile_text_v2("teach me recursion with a tutorial")
    assert ir_v2.persona == "teacher"
    assert "teaching" in ir_v2.intents


def test_compile_v2_non_teaching_prompt_has_no_teaching_intent():
    ir_v2 = compile_text_v2("List three ideas for a birthday gift")
    assert ir_v2.persona == "assistant"
    assert "teaching" not in ir_v2.intents
