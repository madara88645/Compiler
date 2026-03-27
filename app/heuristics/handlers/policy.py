import re

from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class PolicyHandler(BaseHandler):
    """Infer a minimal execution policy from risk, data, and tooling cues."""

    _PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\|/)[^\s]+")
    _FILE_KEYWORDS = (
        "file",
        "path",
        "directory",
        "folder",
        "repo",
        "repository",
        "log",
        "logs",
        "shell",
        "terminal",
        "system",
        "workspace",
    )

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        text = (md.get("original_text") or "").lower()
        risk_flags = list(md.get("risk_flags") or [])
        pii_flags = list(md.get("pii_flags") or [])
        persona_flags = (md.get("persona_evidence") or {}).get("flags") or {}

        policy = ir_v2.policy
        policy.risk_domains = self._unique(risk_flags)

        high_risk = any(flag in {"financial", "health", "legal"} for flag in risk_flags)
        security_risk = "security" in risk_flags

        has_path = bool(self._PATH_PATTERN.search(md.get("original_text") or ""))
        file_or_system_request = has_path or any(keyword in text for keyword in self._FILE_KEYWORDS)
        debug_request = bool(md.get("code_request")) or bool(persona_flags.get("live_debug"))

        if high_risk:
            policy.risk_level = "high"
            policy.execution_mode = "human_approval_required"
        elif security_risk or debug_request or file_or_system_request:
            policy.risk_level = "medium"
            policy.execution_mode = "human_approval_required"

        if debug_request or file_or_system_request:
            policy.allowed_tools = self._unique(
                policy.allowed_tools
                + ["workspace_read"]
                + (["run_tests"] if debug_request else [])
                + (["log_inspection"] if "log" in text or "logs" in text else [])
            )
            policy.forbidden_tools = self._unique(
                policy.forbidden_tools + ["secret_access", "write_outside_workspace"]
            )
            policy.sanitization_rules = self._unique(
                policy.sanitization_rules
                + ["mask_secrets"]
                + (
                    ["path_must_stay_within_workspace"]
                    if has_path or file_or_system_request
                    else []
                )
            )

        if pii_flags:
            severity = (
                "restricted"
                if any(flag in {"credit_card", "iban"} for flag in pii_flags)
                else "confidential"
            )
            policy.data_sensitivity = severity
            policy.sanitization_rules = self._unique(
                policy.sanitization_rules + ["mask_sensitive_values"]
            )
        elif high_risk and policy.data_sensitivity == "public":
            policy.data_sensitivity = "internal"

        ir_v2.metadata["policy_summary"] = policy.model_dump()

    @staticmethod
    def _unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_items: list[str] = []
        for item in items:
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            unique_items.append(value)
        return unique_items
