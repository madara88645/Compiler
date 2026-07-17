"""Unit tests for the IRv2 policy-header formatting helpers in app.emitters.

_policy_summary_text_v2, _top_constraints_text_v2, _policy_check_lines_v2,
_is_benign_policy_v2, and _emit_policy_header_v2 are pure string/bool
formatters reached transitively via emit_expanded_prompt_v2 /
emit_system_prompt_v2 tests, but had no direct unit test pinning their
branches in isolation.
"""

from __future__ import annotations

from app.emitters import (
    _emit_policy_header_v2,
    _is_benign_policy_v2,
    _policy_check_lines_v2,
    _policy_summary_text_v2,
    _top_constraints_text_v2,
)
from app.models_v2 import ConstraintV2, IRv2, PolicyV2


class TestTopConstraintsTextV2:
    def test_empty_list_returns_empty_string(self):
        assert _top_constraints_text_v2([]) == ""

    def test_sorts_by_priority_descending(self):
        cons = [
            ConstraintV2(text="low", priority=10),
            ConstraintV2(text="high", priority=90),
            ConstraintV2(text="mid", priority=50),
        ]
        assert _top_constraints_text_v2(cons) == "high | mid | low"

    def test_respects_limit(self):
        cons = [ConstraintV2(text=f"c{i}", priority=i) for i in range(5)]
        assert _top_constraints_text_v2(cons, limit=2) == "c4 | c3"

    def test_schema_enforcement_id_renders_as_bracketed_label(self):
        cons = [ConstraintV2(id="schema_enforcement", text="ignored text", priority=100)]
        assert _top_constraints_text_v2(cons) == "[JSON Schema Enforced]"


class TestPolicySummaryTextV2:
    def test_includes_risk_and_execution_by_default(self):
        ir = IRv2()
        assert _policy_summary_text_v2(ir) == "risk=low; execution=advice_only"

    def test_includes_domains_forbidden_tools_and_sanitization_when_present(self):
        ir = IRv2(
            policy=PolicyV2(
                risk_level="high",
                execution_mode="human_approval_required",
                risk_domains=["finance", "health"],
                forbidden_tools=["shell", "network"],
                sanitization_rules=["strip_pii"],
            )
        )
        assert _policy_summary_text_v2(ir) == (
            "risk=high; execution=human_approval_required; "
            "domains=finance,health; forbidden_tools=shell,network; "
            "sanitization=strip_pii"
        )

    def test_truncates_lists_to_first_five_entries(self):
        ir = IRv2(policy=PolicyV2(risk_domains=[f"d{i}" for i in range(8)]))
        assert "domains=d0,d1,d2,d3,d4" in _policy_summary_text_v2(ir)
        assert "d5" not in _policy_summary_text_v2(ir)

    def test_omits_data_sensitivity_when_public(self):
        ir = IRv2(policy=PolicyV2(data_sensitivity="public"))
        assert "data=" not in _policy_summary_text_v2(ir)

    def test_includes_data_sensitivity_when_non_public(self):
        ir = IRv2(policy=PolicyV2(data_sensitivity="confidential"))
        assert "data=confidential" in _policy_summary_text_v2(ir)


class TestPolicyCheckLinesV2:
    def test_returns_empty_for_fully_benign_policy(self):
        ir = IRv2(policy=PolicyV2())
        assert _policy_check_lines_v2(ir) == []

    def test_approval_required_line_uses_reason_phrases(self):
        ir = IRv2(
            policy=PolicyV2(execution_mode="human_approval_required"),
            metadata={"policy_reasons": ["debug_request"]},
        )
        lines = _policy_check_lines_v2(ir)
        assert lines[0] == "Approval required because debugging or code execution context."

    def test_non_approval_mode_with_reasons_uses_policy_trigger_line(self):
        ir = IRv2(
            policy=PolicyV2(execution_mode="auto_ok", forbidden_tools=["shell"]),
            metadata={"policy_reasons": ["debug_request"]},
        )
        lines = _policy_check_lines_v2(ir)
        assert lines[0] == "Policy trigger: debugging or code execution context."

    def test_forbidden_tools_line_truncates_to_five(self):
        ir = IRv2(policy=PolicyV2(forbidden_tools=[f"t{i}" for i in range(8)]))
        lines = _policy_check_lines_v2(ir)
        assert lines[-1] == "Do not use: t0, t1, t2, t3, t4."

    def test_sanitization_rules_line_present(self):
        ir = IRv2(policy=PolicyV2(sanitization_rules=["strip_pii", "mask_emails"]))
        lines = _policy_check_lines_v2(ir)
        assert "Apply sanitization: strip_pii, mask_emails." in lines

    def test_data_sensitivity_line_present_when_non_public(self):
        ir = IRv2(policy=PolicyV2(data_sensitivity="restricted"))
        lines = _policy_check_lines_v2(ir)
        assert lines == ["Data sensitivity: restricted."]


class TestIsBenignPolicyV2:
    def test_auto_ok_low_risk_public_policy_is_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low"))
        assert _is_benign_policy_v2(ir) is True

    def test_non_auto_ok_execution_mode_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="human_approval_required"))
        assert _is_benign_policy_v2(ir) is False

    def test_elevated_risk_level_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="medium"))
        assert _is_benign_policy_v2(ir) is False

    def test_non_public_data_sensitivity_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", data_sensitivity="confidential"))
        assert _is_benign_policy_v2(ir) is False

    def test_any_risk_domain_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_domains=["finance"]))
        assert _is_benign_policy_v2(ir) is False

    def test_any_forbidden_tool_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", forbidden_tools=["shell"]))
        assert _is_benign_policy_v2(ir) is False

    def test_any_sanitization_rule_is_not_benign(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", sanitization_rules=["strip_pii"]))
        assert _is_benign_policy_v2(ir) is False


class TestEmitPolicyHeaderV2:
    def test_benign_policy_yields_no_header(self):
        ir = IRv2(policy=PolicyV2(execution_mode="auto_ok", risk_level="low"))
        assert _emit_policy_header_v2(ir) == []

    def test_non_benign_policy_yields_prefixed_summary_line(self):
        ir = IRv2(policy=PolicyV2(execution_mode="human_approval_required", risk_level="high"))
        assert _emit_policy_header_v2(ir) == [
            "Policy: risk=high; execution=human_approval_required"
        ]
