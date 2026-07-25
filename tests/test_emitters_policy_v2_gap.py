"""Coverage for the v2 policy/prompt emitter helpers that had zero prior tests:
emit_user_prompt_v2, _top_constraints_text_v2, _is_benign_policy_v2,
_emit_policy_header_v2, _policy_check_lines_v2, and _is_conservative_mode.
These are pure string-formatting/branching functions that feed directly into
exported prompt text, so a regression here silently changes user-facing output.
"""

import pytest

from app.emitters import (
    _emit_policy_header_v2,
    _is_benign_policy_v2,
    _is_conservative_mode,
    _policy_check_lines_v2,
    _top_constraints_text_v2,
    emit_user_prompt_v2,
)
from app.models_v2 import ConstraintV2, IRv2, PolicyV2


# ---- emit_user_prompt_v2 ----


def test_emit_user_prompt_v2_empty_ir_returns_empty_string():
    assert emit_user_prompt_v2(IRv2()) == ""


def test_emit_user_prompt_v2_renders_all_sections_in_order():
    ir = IRv2(
        goals=["Ship the feature"],
        tasks=["Write the code"],
        inputs={"repo": "compiler", "branch": "main"},
        tools=["shell"],
        examples=["example output"],
    )
    result = emit_user_prompt_v2(ir)
    assert result == (
        "Goals:\n"
        "- Ship the feature\n"
        "Tasks:\n"
        "- Write the code\n"
        "Inputs:\n"
        "- repo: compiler\n"
        "- branch: main\n"
        "Tools:\n"
        "- shell\n"
        "Examples:\n"
        "---\nexample output\n---"
    )


def test_emit_user_prompt_v2_examples_are_fenced_individually():
    ir = IRv2(examples=["first", "second"])
    result = emit_user_prompt_v2(ir)
    assert result == "Examples:\n---\nfirst\n---\n---\nsecond\n---"


# ---- _top_constraints_text_v2 ----


def test_top_constraints_text_v2_empty_list_returns_empty_string():
    assert _top_constraints_text_v2([]) == ""


def test_top_constraints_text_v2_sorts_by_priority_descending_and_limits():
    cons = [
        ConstraintV2(text="low", priority=1),
        ConstraintV2(text="high", priority=90),
        ConstraintV2(text="mid", priority=40),
        ConstraintV2(text="dropped", priority=0),
    ]
    assert _top_constraints_text_v2(cons, limit=3) == "high | mid | low"


def test_top_constraints_text_v2_schema_enforcement_id_is_rewritten():
    cons = [ConstraintV2(id="schema_enforcement", text="irrelevant free text", priority=50)]
    assert _top_constraints_text_v2(cons) == "[JSON Schema Enforced]"


# ---- _is_benign_policy_v2 / _emit_policy_header_v2 ----


def test_is_benign_policy_v2_true_for_auto_ok_low_risk_public_policy():
    ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low", data_sensitivity="public"))
    assert _is_benign_policy_v2(ir) is True


def test_is_benign_policy_v2_false_for_default_advice_only_policy():
    # Default PolicyV2.execution_mode is "advice_only", not "auto_ok" — not benign.
    assert _is_benign_policy_v2(IRv2()) is False


@pytest.mark.parametrize(
    "policy_kwargs",
    [
        {"execution_mode": "human_approval_required"},
        {"risk_level": "high"},
        {"data_sensitivity": "confidential"},
        {"risk_domains": ["finance"]},
        {"forbidden_tools": ["shell"]},
        {"sanitization_rules": ["strip_pii"]},
    ],
)
def test_is_benign_policy_v2_false_when_any_field_is_non_default(policy_kwargs):
    ir = IRv2(policy=PolicyV2(**policy_kwargs))
    assert _is_benign_policy_v2(ir) is False


def test_emit_policy_header_v2_omitted_for_benign_policy():
    ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low", data_sensitivity="public"))
    assert _emit_policy_header_v2(ir) == []


def test_emit_policy_header_v2_present_for_non_benign_policy():
    ir = IRv2(policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"))
    header = _emit_policy_header_v2(ir)
    assert header == ["Policy: risk=high; execution=human_approval_required"]


# ---- _policy_check_lines_v2 ----


def test_policy_check_lines_v2_empty_for_benign_policy():
    assert _policy_check_lines_v2(IRv2()) == []


def test_policy_check_lines_v2_truncates_forbidden_tools_and_sanitization_rules_to_five():
    ir = IRv2(
        policy=PolicyV2(
            forbidden_tools=[f"tool{i}" for i in range(7)],
            sanitization_rules=[f"rule{i}" for i in range(7)],
        )
    )
    lines = _policy_check_lines_v2(ir)
    assert lines == [
        "Do not use: tool0, tool1, tool2, tool3, tool4.",
        "Apply sanitization: rule0, rule1, rule2, rule3, rule4.",
    ]


def test_policy_check_lines_v2_data_sensitivity_line_omitted_when_public():
    ir = IRv2(policy=PolicyV2(execution_mode="human_approval_required"))
    lines = _policy_check_lines_v2(ir)
    assert not any(line.startswith("Data sensitivity:") for line in lines)


def test_policy_check_lines_v2_data_sensitivity_line_present_when_non_public():
    ir = IRv2(policy=PolicyV2(data_sensitivity="confidential"))
    lines = _policy_check_lines_v2(ir)
    assert lines == ["Data sensitivity: confidential."]


# ---- _is_conservative_mode ----


def test_is_conservative_mode_explicit_true_bypasses_env(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
    assert _is_conservative_mode(True) is True


def test_is_conservative_mode_explicit_false_bypasses_env(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
    assert _is_conservative_mode(False) is False


def test_is_conservative_mode_defaults_conservative_when_env_unset(monkeypatch):
    monkeypatch.delenv("PROMPT_COMPILER_MODE", raising=False)
    assert _is_conservative_mode(None) is True


def test_is_conservative_mode_env_default_is_case_insensitive_and_trims_whitespace(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "  DEFAULT  ")
    assert _is_conservative_mode(None) is False


def test_is_conservative_mode_unknown_env_value_falls_back_to_conservative(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "yolo")
    assert _is_conservative_mode(None) is True
