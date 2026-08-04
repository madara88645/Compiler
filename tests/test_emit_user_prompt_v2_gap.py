"""Unit tests for app.emitters.emit_user_prompt_v2.

This pure, deterministic string builder had zero test coverage despite being
used by api/routes/compile.py (fallback / render_v2_prompts / language-
mismatch-correction branches) and by the CLI export/transform commands.
"""

from __future__ import annotations

from app.emitters import emit_user_prompt_v2
from app.models_v2 import IRv2


def test_all_sections_empty_returns_empty_string():
    ir = IRv2()
    assert emit_user_prompt_v2(ir) == ""


def test_goals_section_renders_bulleted_list():
    ir = IRv2(goals=["Ship the feature", "Keep it simple"])
    result = emit_user_prompt_v2(ir)
    assert result == "Goals:\n- Ship the feature\n- Keep it simple"


def test_tasks_section_renders_bulleted_list():
    ir = IRv2(tasks=["Write the code", "Write the tests"])
    result = emit_user_prompt_v2(ir)
    assert result == "Tasks:\n- Write the code\n- Write the tests"


def test_inputs_section_renders_key_value_pairs():
    ir = IRv2(inputs={"language": "python", "framework": "fastapi"})
    result = emit_user_prompt_v2(ir)
    assert result == "Inputs:\n- language: python\n- framework: fastapi"


def test_tools_section_renders_bulleted_list():
    ir = IRv2(tools=["search", "python_exec"])
    result = emit_user_prompt_v2(ir)
    assert result == "Tools:\n- search\n- python_exec"


def test_examples_section_wraps_each_example_in_separators():
    ir = IRv2(examples=["ex one", "ex two"])
    result = emit_user_prompt_v2(ir)
    assert result == "Examples:\n---\nex one\n---\n---\nex two\n---"


def test_sections_render_in_fixed_order_and_are_joined_by_newline():
    ir = IRv2(
        goals=["g1"],
        tasks=["t1"],
        inputs={"k": "v"},
        tools=["tool1"],
        examples=["ex1"],
    )
    result = emit_user_prompt_v2(ir)
    assert result == (
        "Goals:\n- g1\n"
        "Tasks:\n- t1\n"
        "Inputs:\n- k: v\n"
        "Tools:\n- tool1\n"
        "Examples:\n---\nex1\n---"
    )


def test_only_populated_sections_are_included():
    ir = IRv2(goals=["only goals"])
    result = emit_user_prompt_v2(ir)
    assert "Goals:" in result
    assert "Tasks:" not in result
    assert "Inputs:" not in result
    assert "Tools:" not in result
    assert "Examples:" not in result
