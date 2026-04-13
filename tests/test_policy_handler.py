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


def test_policy_does_not_treat_urls_or_abbreviations_as_file_paths():
    ir2 = compile_text_v2(
        "Compare HTTP/2 support and A/B testing patterns from https://example.com/docs."
    )

    assert ir2.policy.risk_level == "low"
    assert ir2.policy.execution_mode == "auto_ok"
    assert "workspace_read" not in ir2.policy.allowed_tools
    assert "path_must_stay_within_workspace" not in ir2.policy.sanitization_rules


# ---------------------------------------------------------------------------
# New: auto_ok, cumulative risk, new domains, paths, domain tools, PII
# ---------------------------------------------------------------------------


def test_policy_auto_ok_for_benign_prompt():
    ir2 = compile_text_v2("Explain the difference between TCP and UDP protocols.")

    assert ir2.policy.risk_level == "low"
    assert ir2.policy.execution_mode == "auto_ok"
    assert ir2.policy.data_sensitivity == "public"


def test_policy_escalates_overlapping_risk_domains():
    ir2 = compile_text_v2(
        "Analyze the legal compliance of my investment portfolio under new SEC regulations."
    )

    assert ir2.policy.risk_level == "high"
    assert ir2.policy.execution_mode == "human_approval_required"
    # Both financial and legal should be detected
    assert "financial" in ir2.policy.risk_domains or "legal" in ir2.policy.risk_domains


def test_policy_detects_privacy_domain():
    ir2 = compile_text_v2(
        "Review our GDPR compliance for personal data processing and consent management."
    )

    assert "privacy" in ir2.policy.risk_domains
    assert ir2.policy.execution_mode == "human_approval_required"
    assert "consent_check" in ir2.policy.sanitization_rules


def test_policy_detects_infrastructure_domain():
    ir2 = compile_text_v2("Plan a Kubernetes deployment strategy with zero-downtime rollback.")

    assert "infrastructure" in ir2.policy.risk_domains
    assert ir2.policy.execution_mode == "human_approval_required"
    assert "dry_run_required" in ir2.policy.sanitization_rules


def test_policy_detects_unc_path():
    ir2 = compile_text_v2(
        "Read the config from \\\\fileserver\\shared\\config.yaml and validate it."
    )

    assert ir2.policy.risk_level in {"medium", "high"}
    assert "workspace_read" in ir2.policy.allowed_tools
    assert "path_must_stay_within_workspace" in ir2.policy.sanitization_rules


def test_policy_detects_cloud_path():
    ir2 = compile_text_v2(
        "Upload the processed dataset to s3://my-bucket/data/output.parquet for analysis."
    )

    assert ir2.policy.risk_level in {"medium", "high"}
    assert "path_must_stay_within_workspace" in ir2.policy.sanitization_rules


def test_policy_domain_tools_financial():
    ir2 = compile_text_v2("Calculate the compound interest on my stock investment over 10 years.")

    assert "financial" in ir2.policy.risk_domains
    assert "calculator" in ir2.policy.allowed_tools
    assert "web_scraper" in ir2.policy.forbidden_tools
    assert "audit_trail" in ir2.policy.sanitization_rules


def test_policy_domain_tools_health():
    ir2 = compile_text_v2(
        "Summarize the latest treatment options for type 2 diabetes from medical journals."
    )

    assert "health" in ir2.policy.risk_domains
    assert "hipaa_filter" in ir2.policy.sanitization_rules
    assert "secret_access" in ir2.policy.forbidden_tools


def test_pii_detects_ssn():
    from app.heuristics import detect_pii

    flags = detect_pii("My SSN is 123-45-6789, please process my application.")
    assert "ssn" in flags
