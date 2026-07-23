"""Unit tests for policy-gating pure helpers in app/emitters.py.

These functions decide whether risk/policy metadata is surfaced or
suppressed in the compiled system prompt, and how conservative mode is
resolved. They are security/policy relevant because a wrong answer here
means a risky request silently loses its policy warning text.

Covers:
- _is_conservative_mode: explicit arg wins over env var; env var fallback;
  default (unset env) behavior.
- _is_benign_policy_v2: true/false branches for each contributing field.
- _policy_check_lines_v2: empty-line short circuit, approval-required
  phrasing, forbidden tools, sanitization rules, data sensitivity.
- _emit_policy_header_v2: suppressed for benign policy, surfaced
  otherwise, and empty when the summary text is empty (defensive branch).
"""

from __future__ import annotations

import pytest

from app.emitters import (
    _is_conservative_mode,
    _is_benign_policy_v2,
    _policy_check_lines_v2,
    _emit_policy_header_v2,
)
from app.models_v2 import IRv2, PolicyV2


def _make_ir(policy: PolicyV2 | None = None, metadata: dict | None = None) -> IRv2:
    return IRv2(policy=policy or PolicyV2(), metadata=metadata or {})


# ---------------------------------------------------------------------------
# _is_conservative_mode
# ---------------------------------------------------------------------------


class TestIsConservativeMode:
    def test_explicit_true_wins_regardless_of_env(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
        assert _is_conservative_mode(True) is True

    def test_explicit_false_wins_regardless_of_env(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
        assert _is_conservative_mode(False) is False

    def test_env_conservative_when_arg_is_none(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
        assert _is_conservative_mode(None) is True

    def test_env_default_disables_conservative(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
        assert _is_conservative_mode(None) is False

    def test_env_default_case_insensitive_and_whitespace_tolerant(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "  DEFAULT  ")
        assert _is_conservative_mode(None) is False

    def test_missing_env_defaults_to_conservative(self, monkeypatch):
        monkeypatch.delenv("PROMPT_COMPILER_MODE", raising=False)
        assert _is_conservative_mode(None) is True

    def test_unrecognized_env_value_is_treated_as_conservative(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "some_other_mode")
        assert _is_conservative_mode(None) is True


# ---------------------------------------------------------------------------
# _is_benign_policy_v2
# ---------------------------------------------------------------------------


class TestIsBenignPolicyV2:
    def test_default_policy_is_not_benign_because_default_execution_mode_is_advice_only(self):
        # PolicyV2()'s default execution_mode is "advice_only", not "auto_ok",
        # so an untouched default policy does NOT count as benign.
        ir = _make_ir()
        assert ir.policy.execution_mode == "advice_only"
        assert _is_benign_policy_v2(ir) is False

    def test_human_approval_required_is_not_benign(self):
        ir = _make_ir(PolicyV2(execution_mode="human_approval_required"))
        assert _is_benign_policy_v2(ir) is False

    def test_high_risk_level_is_not_benign(self):
        ir = _make_ir(PolicyV2(risk_level="high"))
        assert _is_benign_policy_v2(ir) is False

    def test_non_public_data_sensitivity_is_not_benign(self):
        ir = _make_ir(PolicyV2(data_sensitivity="confidential"))
        assert _is_benign_policy_v2(ir) is False

    def test_risk_domains_present_is_not_benign(self):
        ir = _make_ir(PolicyV2(risk_domains=["medical"]))
        assert _is_benign_policy_v2(ir) is False

    def test_forbidden_tools_present_is_not_benign(self):
        ir = _make_ir(PolicyV2(forbidden_tools=["shell_exec"]))
        assert _is_benign_policy_v2(ir) is False

    def test_sanitization_rules_present_is_not_benign(self):
        ir = _make_ir(PolicyV2(sanitization_rules=["strip_pii"]))
        assert _is_benign_policy_v2(ir) is False

    def test_auto_ok_low_public_no_extras_is_benign(self):
        ir = _make_ir(
            PolicyV2(
                execution_mode="auto_ok",
                risk_level="low",
                data_sensitivity="public",
                risk_domains=[],
                forbidden_tools=[],
                sanitization_rules=[],
            )
        )
        assert _is_benign_policy_v2(ir) is True


# ---------------------------------------------------------------------------
# _policy_check_lines_v2
# ---------------------------------------------------------------------------


class TestPolicyCheckLinesV2:
    def test_benign_policy_produces_no_lines(self):
        ir = _make_ir()
        assert _policy_check_lines_v2(ir) == []

    def test_human_approval_required_produces_approval_line(self):
        ir = _make_ir(
            PolicyV2(execution_mode="human_approval_required", risk_level="high"),
            metadata={"policy_reasons": ["debug_request"]},
        )
        lines = _policy_check_lines_v2(ir)
        assert any(line.startswith("Approval required because") for line in lines)
        assert any("debugging or code execution context" in line for line in lines)

    def test_human_approval_required_without_reasons_falls_back_to_risk_level_phrase(self):
        ir = _make_ir(PolicyV2(execution_mode="human_approval_required", risk_level="high"))
        lines = _policy_check_lines_v2(ir)
        assert lines[0] == "Approval required because high risk policy."

    def test_forbidden_tools_present_produces_do_not_use_line(self):
        ir = _make_ir(PolicyV2(forbidden_tools=["shell_exec", "network_call"]))
        lines = _policy_check_lines_v2(ir)
        assert any(line.startswith("Do not use: shell_exec, network_call") for line in lines)

    def test_forbidden_tools_absent_produces_no_do_not_use_line(self):
        ir = _make_ir(PolicyV2(execution_mode="human_approval_required"))
        lines = _policy_check_lines_v2(ir)
        assert not any(line.startswith("Do not use:") for line in lines)

    def test_sanitization_required_produces_sanitize_line(self):
        ir = _make_ir(PolicyV2(sanitization_rules=["strip_pii", "mask_emails"]))
        lines = _policy_check_lines_v2(ir)
        assert any(
            line.startswith("Apply sanitization: strip_pii, mask_emails") for line in lines
        )

    def test_sanitization_not_required_produces_no_sanitize_line(self):
        ir = _make_ir(PolicyV2(execution_mode="human_approval_required"))
        lines = _policy_check_lines_v2(ir)
        assert not any(line.startswith("Apply sanitization:") for line in lines)

    def test_non_public_data_sensitivity_produces_data_sensitivity_line(self):
        ir = _make_ir(PolicyV2(data_sensitivity="confidential"))
        lines = _policy_check_lines_v2(ir)
        assert "Data sensitivity: confidential." in lines

    def test_forbidden_tools_list_is_truncated_to_five(self):
        tools = [f"tool{i}" for i in range(8)]
        ir = _make_ir(PolicyV2(forbidden_tools=tools))
        lines = _policy_check_lines_v2(ir)
        do_not_use_line = next(line for line in lines if line.startswith("Do not use:"))
        assert ", ".join(tools[:5]) in do_not_use_line
        assert "tool6" not in do_not_use_line

    def test_non_approval_with_reasons_uses_policy_trigger_phrasing(self):
        ir = _make_ir(
            PolicyV2(execution_mode="advice_only", forbidden_tools=["shell_exec"]),
            metadata={"policy_reasons": ["overlapping_risk_domains"]},
        )
        lines = _policy_check_lines_v2(ir)
        assert any(line.startswith("Policy trigger: overlapping risk domains") for line in lines)


# ---------------------------------------------------------------------------
# _emit_policy_header_v2
# ---------------------------------------------------------------------------


class TestEmitPolicyHeaderV2:
    def test_benign_policy_suppresses_header(self):
        ir = _make_ir(
            PolicyV2(
                execution_mode="auto_ok",
                risk_level="low",
                data_sensitivity="public",
                risk_domains=[],
                forbidden_tools=[],
                sanitization_rules=[],
            )
        )
        assert _emit_policy_header_v2(ir) == []

    def test_untouched_default_policy_surfaces_header(self):
        # Default execution_mode is "advice_only" (not benign's "auto_ok"),
        # so a completely default policy still surfaces a header line.
        ir = _make_ir()
        header = _emit_policy_header_v2(ir)
        assert header == ["Policy: risk=low; execution=advice_only"]

    def test_non_benign_policy_surfaces_header(self):
        ir = _make_ir(PolicyV2(execution_mode="human_approval_required", risk_level="high"))
        header = _emit_policy_header_v2(ir)
        assert len(header) == 1
        assert header[0].startswith("Policy: ")
        assert "risk=high" in header[0]
        assert "execution=human_approval_required" in header[0]

    def test_header_includes_forbidden_tools_and_sanitization(self):
        ir = _make_ir(
            PolicyV2(
                risk_level="medium",
                forbidden_tools=["shell_exec"],
                sanitization_rules=["strip_pii"],
            )
        )
        header = _emit_policy_header_v2(ir)
        assert header
        assert "forbidden_tools=shell_exec" in header[0]
        assert "sanitization=strip_pii" in header[0]

    def test_header_includes_risk_domains_and_data_sensitivity(self):
        ir = _make_ir(
            PolicyV2(
                risk_level="high",
                risk_domains=["medical", "legal"],
                data_sensitivity="confidential",
            )
        )
        header = _emit_policy_header_v2(ir)
        assert header
        assert "domains=medical,legal" in header[0]
        assert "data=confidential" in header[0]
