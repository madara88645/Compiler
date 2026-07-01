"""Unit tests for pure IR v2 policy/domain-suggestion helpers in app/emitters.py.

Functions under test build human-readable policy summaries and domain
suggestion lists purely from an IRv2 object's fields/metadata — no I/O,
no env reads, no model calls.
"""

from __future__ import annotations

from app.emitters import (
    _domain_suggestions_v2,
    _policy_reason_phrases_v2,
    _policy_summary_text_v2,
)
from app.models_v2 import IRv2, PolicyV2


def make_ir(*, policy: PolicyV2 | None = None, metadata: dict | None = None) -> IRv2:
    return IRv2(policy=policy or PolicyV2(), metadata=metadata or {})


class TestPolicySummaryTextV2:
    def test_default_policy_has_risk_and_execution_only(self) -> None:
        ir = make_ir()
        assert _policy_summary_text_v2(ir) == "risk=low; execution=advice_only"

    def test_includes_risk_domains_capped_at_five(self) -> None:
        ir = make_ir(policy=PolicyV2(risk_domains=["a", "b", "c", "d", "e", "f"]))
        summary = _policy_summary_text_v2(ir)
        assert "domains=a,b,c,d,e" in summary
        assert "f" not in summary.split("domains=")[1]

    def test_includes_forbidden_tools_capped_at_five(self) -> None:
        ir = make_ir(policy=PolicyV2(forbidden_tools=["t1", "t2", "t3", "t4", "t5", "t6"]))
        summary = _policy_summary_text_v2(ir)
        assert "forbidden_tools=t1,t2,t3,t4,t5" in summary
        assert "t6" not in summary

    def test_includes_sanitization_rules_capped_at_five(self) -> None:
        ir = make_ir(policy=PolicyV2(sanitization_rules=["s1", "s2", "s3", "s4", "s5", "s6"]))
        summary = _policy_summary_text_v2(ir)
        assert "sanitization=s1,s2,s3,s4,s5" in summary
        assert "s6" not in summary

    def test_non_public_data_sensitivity_included(self) -> None:
        ir = make_ir(policy=PolicyV2(data_sensitivity="confidential"))
        assert "data=confidential" in _policy_summary_text_v2(ir)

    def test_public_data_sensitivity_omitted(self) -> None:
        ir = make_ir(policy=PolicyV2(data_sensitivity="public"))
        assert "data=" not in _policy_summary_text_v2(ir)

    def test_parts_joined_with_semicolon_space(self) -> None:
        ir = make_ir(policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"))
        assert _policy_summary_text_v2(ir) == "risk=high; execution=human_approval_required"

    def test_all_fields_combined(self) -> None:
        ir = make_ir(
            policy=PolicyV2(
                risk_level="high",
                execution_mode="human_approval_required",
                risk_domains=["finance"],
                forbidden_tools=["shell"],
                sanitization_rules=["redact_pii"],
                data_sensitivity="pii",
            )
        )
        summary = _policy_summary_text_v2(ir)
        assert summary == (
            "risk=high; execution=human_approval_required; domains=finance; "
            "forbidden_tools=shell; sanitization=redact_pii; data=pii"
        )


class TestPolicyReasonPhrasesV2:
    def test_no_reasons_and_not_approval_required_returns_empty(self) -> None:
        ir = make_ir()
        assert _policy_reason_phrases_v2(ir) == []

    def test_no_reasons_but_approval_required_falls_back_to_risk_level(self) -> None:
        ir = make_ir(policy=PolicyV2(risk_level="high", execution_mode="human_approval_required"))
        assert _policy_reason_phrases_v2(ir) == ["high risk policy"]

    def test_high_risk_domain_reason_formatted(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["high_risk_domain:finance"]})
        assert _policy_reason_phrases_v2(ir) == ["high-risk domain: finance"]

    def test_risk_domain_reason_formatted(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["risk_domain:legal"]})
        assert _policy_reason_phrases_v2(ir) == ["risk domain: legal"]

    def test_pii_detected_reason_formatted(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["pii_detected:email"]})
        assert _policy_reason_phrases_v2(ir) == ["sensitive data detected: email"]

    def test_overlapping_risk_domains_literal_phrase(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["overlapping_risk_domains"]})
        assert _policy_reason_phrases_v2(ir) == ["overlapping risk domains"]

    def test_debug_request_literal_phrase(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["debug_request"]})
        assert _policy_reason_phrases_v2(ir) == ["debugging or code execution context"]

    def test_file_or_system_request_literal_phrase(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["file_or_system_request"]})
        assert _policy_reason_phrases_v2(ir) == ["file or system access requested"]

    def test_unknown_reason_underscores_replaced_with_spaces(self) -> None:
        ir = make_ir(metadata={"policy_reasons": ["some_custom_reason"]})
        assert _policy_reason_phrases_v2(ir) == ["some custom reason"]

    def test_non_string_reasons_are_skipped(self) -> None:
        ir = make_ir(metadata={"policy_reasons": [123, None, "debug_request"]})
        assert _policy_reason_phrases_v2(ir) == ["debugging or code execution context"]

    def test_multiple_reasons_preserve_order(self) -> None:
        ir = make_ir(
            metadata={
                "policy_reasons": [
                    "debug_request",
                    "high_risk_domain:crypto",
                    "overlapping_risk_domains",
                ]
            }
        )
        assert _policy_reason_phrases_v2(ir) == [
            "debugging or code execution context",
            "high-risk domain: crypto",
            "overlapping risk domains",
        ]

    def test_missing_metadata_key_treated_as_empty(self) -> None:
        ir = make_ir(metadata={"other_key": "value"})
        assert _policy_reason_phrases_v2(ir) == []


class TestDomainSuggestionsV2:
    def test_no_metadata_returns_empty_list(self) -> None:
        ir = make_ir()
        assert _domain_suggestions_v2(ir) == []

    def test_non_list_metadata_returns_empty_list(self) -> None:
        ir = make_ir(metadata={"domain_suggestions": "not-a-list"})
        assert _domain_suggestions_v2(ir) == []

    def test_non_dict_items_are_skipped(self) -> None:
        ir = make_ir(metadata={"domain_suggestions": ["not-a-dict", 123]})
        assert _domain_suggestions_v2(ir) == []

    def test_empty_text_items_are_skipped(self) -> None:
        ir = make_ir(metadata={"domain_suggestions": [{"text": "", "priority": 5}]})
        assert _domain_suggestions_v2(ir) == []

    def test_sorted_by_priority_descending(self) -> None:
        ir = make_ir(
            metadata={
                "domain_suggestions": [
                    {"text": "low priority tip", "priority": 1},
                    {"text": "high priority tip", "priority": 9},
                    {"text": "mid priority tip", "priority": 5},
                ]
            }
        )
        assert _domain_suggestions_v2(ir) == [
            "high priority tip",
            "mid priority tip",
            "low priority tip",
        ]

    def test_limit_truncates_results(self) -> None:
        ir = make_ir(
            metadata={
                "domain_suggestions": [
                    {"text": f"tip {i}", "priority": i} for i in range(5)
                ]
            }
        )
        assert _domain_suggestions_v2(ir, limit=2) == ["tip 4", "tip 3"]

    def test_duplicate_text_case_insensitive_deduplicated(self) -> None:
        ir = make_ir(
            metadata={
                "domain_suggestions": [
                    {"text": "Use HTTPS", "priority": 5},
                    {"text": "use https", "priority": 1},
                ]
            }
        )
        assert _domain_suggestions_v2(ir) == ["Use HTTPS"]

    def test_missing_priority_defaults_to_zero(self) -> None:
        ir = make_ir(metadata={"domain_suggestions": [{"text": "no priority set"}]})
        assert _domain_suggestions_v2(ir) == ["no priority set"]

    def test_non_numeric_priority_defaults_to_zero(self) -> None:
        ir = make_ir(
            metadata={"domain_suggestions": [{"text": "bad priority", "priority": "high"}]}
        )
        assert _domain_suggestions_v2(ir) == ["bad priority"]

    def test_text_is_cleaned_via_clean_domain_suggestion_text(self) -> None:
        ir = make_ir(
            metadata={
                "domain_suggestions": [
                    {"text": "  Include   retry logic  ", "priority": 1}
                ]
            }
        )
        assert _domain_suggestions_v2(ir) == ["Include retry logic"]
