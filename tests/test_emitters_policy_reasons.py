"""_policy_reason_phrases_v2 translates raw policy_reasons metadata codes into
human-readable phrases used in the emitted policy header. Each prefix/code has
its own branch; a regression here would silently show the wrong reason to users.
"""

from app.emitters import _policy_reason_phrases_v2
from app.models_v2 import IRv2, PolicyV2


def test_all_known_reason_codes_map_to_expected_phrases():
    ir = IRv2(
        metadata={
            "policy_reasons": [
                "high_risk_domain:finance",
                "pii_detected:email",
                "overlapping_risk_domains",
                "debug_request",
                "file_or_system_request",
                "risk_domain:health",
            ]
        }
    )
    assert _policy_reason_phrases_v2(ir) == [
        "high-risk domain: finance",
        "sensitive data detected: email",
        "overlapping risk domains",
        "debugging or code execution context",
        "file or system access requested",
        "risk domain: health",
    ]


def test_unknown_reason_code_falls_back_to_underscore_replacement():
    ir = IRv2(metadata={"policy_reasons": ["some_other_flag"]})
    assert _policy_reason_phrases_v2(ir) == ["some other flag"]


def test_non_string_reason_entries_are_skipped():
    ir = IRv2(metadata={"policy_reasons": [123, "debug_request", None]})
    assert _policy_reason_phrases_v2(ir) == ["debugging or code execution context"]


def test_no_reasons_but_human_approval_required_falls_back_to_risk_level():
    ir = IRv2(metadata={}, policy=PolicyV2(execution_mode="human_approval_required", risk_level="high"))
    assert _policy_reason_phrases_v2(ir) == ["high risk policy"]


def test_no_reasons_and_advice_only_mode_yields_empty_list():
    ir = IRv2(metadata={}, policy=PolicyV2(execution_mode="advice_only"))
    assert _policy_reason_phrases_v2(ir) == []
