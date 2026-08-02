"""Direct unit tests for emit_user_prompt_v2, which builds the v2
user-prompt string from an IRv2 and previously had no dedicated test file.
"""
from app.emitters import emit_user_prompt_v2
from app.models_v2 import IRv2


def test_emit_user_prompt_v2_empty_ir():
    ir = IRv2()
    assert emit_user_prompt_v2(ir) == ""


def test_emit_user_prompt_v2_goals_only():
    ir = IRv2(goals=["Ship the feature"])
    result = emit_user_prompt_v2(ir)
    assert result == "Goals:\n- Ship the feature"


def test_emit_user_prompt_v2_tasks_only():
    ir = IRv2(tasks=["Write tests", "Open PR"])
    result = emit_user_prompt_v2(ir)
    assert result == "Tasks:\n- Write tests\n- Open PR"


def test_emit_user_prompt_v2_inputs_only():
    ir = IRv2(inputs={"repo": "compiler", "branch": "main"})
    result = emit_user_prompt_v2(ir)
    assert result == "Inputs:\n- repo: compiler\n- branch: main"


def test_emit_user_prompt_v2_tools_only():
    ir = IRv2(tools=["search", "calculator"])
    result = emit_user_prompt_v2(ir)
    assert result == "Tools:\n- search\n- calculator"


def test_emit_user_prompt_v2_examples_only():
    ir = IRv2(examples=["input -> output"])
    result = emit_user_prompt_v2(ir)
    assert result == "Examples:\n---\ninput -> output\n---"


def test_emit_user_prompt_v2_all_fields_combined():
    ir = IRv2(
        goals=["Goal A"],
        tasks=["Task A"],
        inputs={"key": "value"},
        tools=["tool A"],
        examples=["example A"],
    )
    result = emit_user_prompt_v2(ir)
    assert result.startswith("Goals:\n- Goal A\nTasks:\n- Task A\n")
    assert "Inputs:\n- key: value" in result
    assert "Tools:\n- tool A" in result
    assert result.endswith("Examples:\n---\nexample A\n---")
