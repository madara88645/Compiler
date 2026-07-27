"""_is_benign_policy_v2 / _policy_summary_text_v2 / _policy_check_lines_v2 decide
whether a policy header is shown at all and what it says. A regression here
would either hide a real policy warning from the user or spam a benign
request with an empty/misleading header.
"""

from app.emitters import (
    _is_benign_policy_v2,
    _policy_check_lines_v2,
    _policy_summary_text_v2,
)
from app.models_v2 import IRv2, PolicyV2


def _ir(**policy_kwargs):
    return IRv2(policy=PolicyV2(**policy_kwargs))


def test_default_policy_is_not_benign_because_default_execution_mode_is_advice_only():
    assert _is_benign_policy_v2(IRv2()) is False


def test_fully_auto_ok_policy_with_no_extras_is_benign():
    ir = _ir(execution_mode="auto_ok", risk_level="low", data_sensitivity="public")
    assert _is_benign_policy_v2(ir) is True


def test_risk_domains_make_an_otherwise_benign_policy_not_benign():
    ir = _ir(
        execution_mode="auto_ok",
        risk_level="low",
        data_sensitivity="public",
        risk_domains=["finance"],
    )
    assert _is_benign_policy_v2(ir) is False


def test_forbidden_tools_make_an_otherwise_benign_policy_not_benign():
    ir = _ir(
        execution_mode="auto_ok",
        risk_level="low",
        data_sensitivity="public",
        forbidden_tools=["shell"],
    )
    assert _is_benign_policy_v2(ir) is False


def test_non_public_data_sensitivity_makes_a_policy_not_benign():
    ir = _ir(execution_mode="auto_ok", risk_level="low", data_sensitivity="confidential")
    assert _is_benign_policy_v2(ir) is False


def test_summary_text_for_minimal_policy_only_shows_risk_and_execution():
    ir = IRv2()
    assert _policy_summary_text_v2(ir) == "risk=low; execution=advice_only"


def test_summary_text_includes_all_populated_fields_in_order():
    ir = _ir(
        risk_level="high",
        execution_mode="human_approval_required",
        risk_domains=["finance", "health"],
        forbidden_tools=["shell", "browser"],
        sanitization_rules=["strip_pii"],
        data_sensitivity="confidential",
    )
    assert _policy_summary_text_v2(ir) == (
        "risk=high; execution=human_approval_required; "
        "domains=finance,health; forbidden_tools=shell,browser; "
        "sanitization=strip_pii; data=confidential"
    )


def test_summary_text_omits_data_sensitivity_when_it_is_public():
    ir = _ir(risk_level="low", execution_mode="advice_only", data_sensitivity="public")
    assert "data=" not in _policy_summary_text_v2(ir)


def test_summary_text_truncates_each_list_field_to_five_entries():
    ir = _ir(risk_domains=[f"domain{i}" for i in range(8)])
    summary = _policy_summary_text_v2(ir)
    domains_part = [p for p in summary.split("; ") if p.startswith("domains=")][0]
    assert domains_part == "domains=domain0,domain1,domain2,domain3,domain4"


def test_check_lines_are_empty_for_a_fully_benign_shaped_policy():
    ir = IRv2(
        policy=PolicyV2(execution_mode="advice_only", data_sensitivity="public"),
        metadata={"policy_reasons": ["debug_request"]},
    )
    # Early-return guard fires purely on policy shape; metadata reasons never
    # get surfaced unless execution_mode/forbidden_tools/sanitization/data
    # sensitivity say otherwise.
    assert _policy_check_lines_v2(ir) == []


def test_check_lines_explain_approval_requirement_using_reason_fallback():
    ir = _ir(execution_mode="human_approval_required", risk_level="high")
    assert _policy_check_lines_v2(ir) == ["Approval required because high risk policy."]


def test_check_lines_include_policy_trigger_when_reasons_present_but_not_blocked():
    ir = IRv2(
        policy=PolicyV2(execution_mode="advice_only", forbidden_tools=["shell"]),
        metadata={"policy_reasons": ["debug_request"]},
    )
    assert _policy_check_lines_v2(ir) == [
        "Policy trigger: debugging or code execution context.",
        "Do not use: shell.",
    ]


def test_check_lines_list_forbidden_tools_and_sanitization_and_data_sensitivity():
    ir = _ir(
        forbidden_tools=["shell", "browser"],
        sanitization_rules=["strip_pii"],
        data_sensitivity="confidential",
    )
    assert _policy_check_lines_v2(ir) == [
        "Do not use: shell, browser.",
        "Apply sanitization: strip_pii.",
        "Data sensitivity: confidential.",
    ]


def test_check_lines_truncate_forbidden_tools_list_to_five():
    ir = _ir(forbidden_tools=[f"tool{i}" for i in range(8)])
    lines = _policy_check_lines_v2(ir)
    assert lines == ["Do not use: tool0, tool1, tool2, tool3, tool4."]
