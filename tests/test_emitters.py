from app.compiler import compile_text
from app.emitters import emit_system_prompt, emit_user_prompt, emit_plan
from app.models import IR


def test_emitters_non_empty():
    ir = compile_text("Explain API design principles in detail")
    assert emit_system_prompt(ir)
    assert emit_user_prompt(ir)
    assert emit_plan(ir)


def test_emit_plan_fallback():
    ir = IR(
        language="en",
        persona="developer",
        role="Senior software engineer",
        domain="General",
        output_format="markdown",
        length_hint="short",
        goals=["Test fallback"],
        tasks=[],
        steps=[],
    )
    plan_str = emit_plan(ir)
    assert plan_str == "1. Analyze request\n   Rationale: establish understanding"


def test_emit_plan_with_steps():
    ir = IR(
        language="en",
        persona="developer",
        role="Senior software engineer",
        domain="General",
        output_format="markdown",
        length_hint="short",
        goals=["Test steps"],
        tasks=[],
        steps=["First step", "Second step"],
    )
    plan_str = emit_plan(ir)
    assert "1. First step" in plan_str
    assert "2. Second step" in plan_str
    assert "Rationale: execute task effectively" in plan_str


def test_emit_plan_with_tasks_as_fallback():
    ir = IR(
        language="en",
        persona="developer",
        role="Senior software engineer",
        domain="General",
        output_format="markdown",
        length_hint="short",
        goals=["Test tasks"],
        tasks=["First task", "Second task"],
        steps=[],
    )
    plan_str = emit_plan(ir)
    assert "1. First task" in plan_str
    assert "2. Second task" in plan_str
    assert "Rationale: execute task effectively" in plan_str
