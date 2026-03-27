from app.compiler import compile_text_v2


def test_policy_marks_financial_prompt_high_risk():
    ir2 = compile_text_v2(
        "Analyze my stock portfolio allocation and suggest an investment strategy."
    )

    assert ir2.policy.risk_level == "high"
    assert "financial" in ir2.policy.risk_domains
    assert ir2.policy.execution_mode == "human_approval_required"


def test_policy_adds_sanitization_and_tool_bounds_for_debug_file_prompts():
    ir2 = compile_text_v2(
        "Debug this Python traceback from my repository and inspect logs in C:\\app\\logs."
    )

    assert ir2.policy.risk_level in {"medium", "high"}
    assert ir2.policy.execution_mode == "human_approval_required"
    assert "workspace_read" in ir2.policy.allowed_tools
    assert "log_inspection" in ir2.policy.allowed_tools
    assert "secret_access" in ir2.policy.forbidden_tools
    assert "path_must_stay_within_workspace" in ir2.policy.sanitization_rules
    assert "mask_secrets" in ir2.policy.sanitization_rules


def test_policy_detects_sensitive_data_and_tightens_sensitivity():
    ir2 = compile_text_v2("Summarize this support ticket and email me at memo@example.com.")

    assert ir2.policy.data_sensitivity in {"confidential", "restricted"}
    assert "mask_sensitive_values" in ir2.policy.sanitization_rules
