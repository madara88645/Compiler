"""Pure unit tests for the v2 policy-header emission helpers in app/emitters.py.

These functions decide what safety/policy text (if any) gets prepended to a
compiled prompt. They are pure string/predicate transforms over IRv2/PolicyV2/
ConstraintV2 objects, so they can be tested directly without invoking the
compiler or any LLM call.
"""

import os

import pytest

from app.emitters import (
    _emit_policy_header_v2,
    _is_benign_policy_v2,
    _is_conservative_mode,
    _policy_check_lines_v2,
    _policy_summary_text_v2,
    _top_constraints_text_v2,
)
from app.models_v2 import ConstraintV2, IRv2, PolicyV2


# ---------------------------------------------------------------------------
# _is_benign_policy_v2
# ---------------------------------------------------------------------------


def test_is_benign_policy_true_for_auto_ok_low_risk_public_policy():
    ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low", data_sensitivity="public"))
    assert _is_benign_policy_v2(ir) is True


def test_is_benign_policy_false_for_default_policy_since_execution_mode_is_advice_only():
    ir = IRv2()
    assert _is_benign_policy_v2(ir) is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_mode": "human_approval_required"},
        {"risk_level": "high"},
        {"data_sensitivity": "confidential"},
        {"risk_domains": ["finance"]},
        {"forbidden_tools": ["shell"]},
        {"sanitization_rules": ["strip_pii"]},
    ],
)
def test_is_benign_policy_false_when_any_field_is_non_benign(overrides):
    base = {"execution_mode": "auto_ok", "risk_level": "low", "data_sensitivity": "public"}
    ir = IRv2(policy=PolicyV2(**{**base, **overrides}))
    assert _is_benign_policy_v2(ir) is False


# ---------------------------------------------------------------------------
# _policy_summary_text_v2
# ---------------------------------------------------------------------------


def test_policy_summary_text_includes_only_risk_and_execution_by_default():
    ir = IRv2()
    assert _policy_summary_text_v2(ir) == "risk=low; execution=advice_only"


def test_policy_summary_text_includes_all_optional_parts_when_present():
    ir = IRv2(
        policy=PolicyV2(
            risk_level="high",
            execution_mode="human_approval_required",
            risk_domains=["finance", "health"],
            forbidden_tools=["shell", "browser"],
            sanitization_rules=["strip_pii"],
            data_sensitivity="confidential",
        )
    )
    assert _policy_summary_text_v2(ir) == (
        "risk=high; execution=human_approval_required; domains=finance,health; "
        "forbidden_tools=shell,browser; sanitization=strip_pii; data=confidential"
    )


def test_policy_summary_text_omits_data_sensitivity_when_public():
    ir = IRv2(policy=PolicyV2(data_sensitivity="public"))
    assert "data=" not in _policy_summary_text_v2(ir)


def test_policy_summary_text_truncates_lists_to_five_entries():
    ir = IRv2(policy=PolicyV2(risk_domains=[f"domain{i}" for i in range(8)]))
    summary = _policy_summary_text_v2(ir)
    domains_part = [p for p in summary.split("; ") if p.startswith("domains=")][0]
    assert domains_part == "domains=domain0,domain1,domain2,domain3,domain4"


# ---------------------------------------------------------------------------
# _policy_check_lines_v2
# ---------------------------------------------------------------------------


def test_policy_check_lines_empty_for_benign_public_advice_only_policy():
    ir = IRv2(policy=PolicyV2())
    assert _policy_check_lines_v2(ir) == []


def test_policy_check_lines_approval_required_uses_reason_phrases():
    ir = IRv2(
        policy=PolicyV2(execution_mode="human_approval_required"),
        metadata={"policy_reasons": ["debug_request"]},
    )
    lines = _policy_check_lines_v2(ir)
    assert lines[0] == "Approval required because debugging or code execution context."


def test_policy_check_lines_non_approval_with_reasons_uses_policy_trigger_prefix():
    ir = IRv2(
        policy=PolicyV2(execution_mode="advice_only", forbidden_tools=["shell"]),
        metadata={"policy_reasons": ["debug_request"]},
    )
    lines = _policy_check_lines_v2(ir)
    assert lines[0] == "Policy trigger: debugging or code execution context."


def test_policy_check_lines_includes_forbidden_tools_and_sanitization_and_sensitivity():
    ir = IRv2(
        policy=PolicyV2(
            execution_mode="advice_only",
            forbidden_tools=["shell", "browser"],
            sanitization_rules=["strip_pii"],
            data_sensitivity="confidential",
        )
    )
    lines = _policy_check_lines_v2(ir)
    assert "Do not use: shell, browser." in lines
    assert "Apply sanitization: strip_pii." in lines
    assert "Data sensitivity: confidential." in lines


def test_policy_check_lines_truncates_forbidden_tools_and_sanitization_to_five():
    ir = IRv2(
        policy=PolicyV2(
            forbidden_tools=[f"tool{i}" for i in range(8)],
            sanitization_rules=[f"rule{i}" for i in range(8)],
        )
    )
    lines = _policy_check_lines_v2(ir)
    do_not_use = next(line for line in lines if line.startswith("Do not use:"))
    apply_sanitization = next(line for line in lines if line.startswith("Apply sanitization:"))
    assert do_not_use == "Do not use: tool0, tool1, tool2, tool3, tool4."
    assert apply_sanitization == "Apply sanitization: rule0, rule1, rule2, rule3, rule4."


# ---------------------------------------------------------------------------
# _emit_policy_header_v2
# ---------------------------------------------------------------------------


def test_emit_policy_header_empty_for_benign_policy():
    ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low", data_sensitivity="public"))
    assert _emit_policy_header_v2(ir) == []


def test_emit_policy_header_wraps_summary_with_policy_prefix():
    ir = IRv2(policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"))
    assert _emit_policy_header_v2(ir) == [
        "Policy: risk=high; execution=human_approval_required"
    ]


# ---------------------------------------------------------------------------
# _top_constraints_text_v2
# ---------------------------------------------------------------------------


def test_top_constraints_text_empty_for_no_constraints():
    assert _top_constraints_text_v2([]) == ""


def test_top_constraints_text_sorts_by_priority_descending():
    constraints = [
        ConstraintV2(text="low priority", priority=10),
        ConstraintV2(text="high priority", priority=90),
        ConstraintV2(text="mid priority", priority=50),
    ]
    assert _top_constraints_text_v2(constraints) == (
        "high priority | mid priority | low priority"
    )


def test_top_constraints_text_respects_limit():
    constraints = [ConstraintV2(text=f"c{i}", priority=i) for i in range(5)]
    result = _top_constraints_text_v2(constraints, limit=2)
    assert result == "c4 | c3"


def test_top_constraints_text_special_cases_schema_enforcement_id():
    constraints = [ConstraintV2(id="schema_enforcement", text="ignored raw text", priority=99)]
    assert _top_constraints_text_v2(constraints) == "[JSON Schema Enforced]"


# ---------------------------------------------------------------------------
# _is_conservative_mode
# ---------------------------------------------------------------------------


def test_is_conservative_mode_explicit_true():
    assert _is_conservative_mode(True) is True


def test_is_conservative_mode_explicit_false():
    assert _is_conservative_mode(False) is False


def test_is_conservative_mode_defaults_to_conservative_when_env_unset(monkeypatch):
    monkeypatch.delenv("PROMPT_COMPILER_MODE", raising=False)
    assert _is_conservative_mode(None) is True


def test_is_conservative_mode_env_default_disables_conservative(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
    assert _is_conservative_mode(None) is False


def test_is_conservative_mode_env_other_value_is_conservative(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "STRICT")
    assert _is_conservative_mode(None) is True
