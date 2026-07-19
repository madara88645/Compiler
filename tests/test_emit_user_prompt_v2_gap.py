from app.emitters import emit_user_prompt_v2
from app.models_v2 import IRv2


def _ir(**overrides) -> IRv2:
    return IRv2(**overrides)


def test_emit_user_prompt_v2_empty_ir_returns_empty_string():
    assert emit_user_prompt_v2(_ir()) == ""


def test_emit_user_prompt_v2_includes_goals_section():
    ir = _ir(goals=["Ship the feature", "Keep it simple"])
    out = emit_user_prompt_v2(ir)
    assert "Goals:" in out
    assert "- Ship the feature" in out
    assert "- Keep it simple" in out


def test_emit_user_prompt_v2_includes_tasks_section():
    ir = _ir(tasks=["Write tests", "Open a PR"])
    out = emit_user_prompt_v2(ir)
    assert "Tasks:" in out
    assert "- Write tests" in out
    assert "- Open a PR" in out


def test_emit_user_prompt_v2_includes_inputs_as_key_value_lines():
    ir = _ir(inputs={"repo": "compiler", "branch": "main"})
    out = emit_user_prompt_v2(ir)
    assert "Inputs:" in out
    assert "- repo: compiler" in out
    assert "- branch: main" in out


def test_emit_user_prompt_v2_includes_tools_section():
    ir = _ir(tools=["pytest", "ruff"])
    out = emit_user_prompt_v2(ir)
    assert "Tools:" in out
    assert "- pytest" in out
    assert "- ruff" in out


def test_emit_user_prompt_v2_includes_examples_fenced_by_dashes():
    ir = _ir(examples=["print('hi')"])
    out = emit_user_prompt_v2(ir)
    assert "Examples:" in out
    assert "---\nprint('hi')\n---" in out


def test_emit_user_prompt_v2_preserves_section_order():
    ir = _ir(
        goals=["g1"],
        tasks=["t1"],
        inputs={"k": "v"},
        tools=["tool1"],
        examples=["ex1"],
    )
    out = emit_user_prompt_v2(ir)
    sections = ["Goals:", "Tasks:", "Inputs:", "Tools:", "Examples:"]
    positions = [out.index(section) for section in sections]
    assert positions == sorted(positions)


def test_emit_user_prompt_v2_omits_sections_with_no_data():
    ir = _ir(goals=["only goal"])
    out = emit_user_prompt_v2(ir)
    assert "Goals:" in out
    assert "Tasks:" not in out
    assert "Inputs:" not in out
    assert "Tools:" not in out
    assert "Examples:" not in out
