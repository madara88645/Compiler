import re

from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class PolicyHandler(BaseHandler):
    """Infer a minimal execution policy from risk, data, and tooling cues."""

    _URL_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://\S+")
    _WINDOWS_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\(?:[^\s\\]+\\)*[^\s\\]+\b")
    _POSIX_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)+[^/\s]+")
    _RELATIVE_FILE_PATTERN = re.compile(
        r"(?<![:/\w])(?:\.{1,2}[\\/])?(?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9]{1,8}\b"
    )
    _UNC_PATH_PATTERN = re.compile(r"\\\\[^\s\\]+\\[^\s]+")
    _CLOUD_PATH_PATTERN = re.compile(r"\b(?:s3|gs|gcs|az|abfss|hdfs)://[^\s]+")

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

    _DOMAIN_TOOL_RULES: dict[str, dict[str, list[str]]] = {
        "financial": {
            "allowed": ["calculator", "spreadsheet_read"],
            "forbidden": ["web_scraper", "secret_access"],
            "sanitization": ["mask_sensitive_values", "audit_trail"],
        },
        "health": {
            "allowed": ["reference_lookup"],
            "forbidden": ["secret_access", "write_outside_workspace"],
            "sanitization": ["mask_sensitive_values", "hipaa_filter"],
        },
        "security": {
            "allowed": ["workspace_read", "run_tests", "log_inspection"],
            "forbidden": ["secret_access", "network_scan"],
            "sanitization": ["mask_secrets", "path_must_stay_within_workspace"],
        },
        "infrastructure": {
            "allowed": ["workspace_read", "run_tests"],
            "forbidden": ["production_write", "secret_access"],
            "sanitization": ["mask_secrets", "dry_run_required"],
        },
        "privacy": {
            "allowed": ["workspace_read"],
            "forbidden": ["secret_access", "external_share"],
            "sanitization": ["mask_sensitive_values", "consent_check"],
        },
    }

    _HIGH_RISK_DOMAINS = {"financial", "health", "legal"}

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        md = ir_v1.metadata or {}
        original_text = md.get("original_text") or ""
        text = original_text.lower()
        risk_flags = list(md.get("risk_flags") or [])
        pii_flags = list(md.get("pii_flags") or [])
        persona_flags = (md.get("persona_evidence") or {}).get("flags") or {}

        policy = ir_v2.policy
        policy.risk_domains = self._unique(risk_flags)

        has_high_risk_domain = any(flag in self._HIGH_RISK_DOMAINS for flag in risk_flags)
        risk_score = len(set(risk_flags))

        has_path = self._has_explicit_path(original_text)
        file_or_system_request = has_path or any(keyword in text for keyword in self._FILE_KEYWORDS)
        debug_request = bool(md.get("code_request")) or bool(persona_flags.get("live_debug"))

        # Cumulative risk scoring: 2+ overlapping domains always escalate
        if risk_score >= 2 or has_high_risk_domain:
            policy.risk_level = "high"
            policy.execution_mode = "human_approval_required"
        elif risk_score == 1 or debug_request or file_or_system_request:
            policy.risk_level = "medium"
            policy.execution_mode = "human_approval_required"
        else:
            policy.execution_mode = "auto_ok"

        # Domain-specific tool control
        for domain in risk_flags:
            rules = self._DOMAIN_TOOL_RULES.get(domain)
            if rules:
                policy.allowed_tools = self._unique(policy.allowed_tools + rules["allowed"])
                policy.forbidden_tools = self._unique(policy.forbidden_tools + rules["forbidden"])
                policy.sanitization_rules = self._unique(
                    policy.sanitization_rules + rules["sanitization"]
                )

        # Generic debug/file request tool bounds (additive to domain rules)
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
        elif has_high_risk_domain and policy.data_sensitivity == "public":
            policy.data_sensitivity = "internal"

        ir_v2.metadata["policy_summary"] = policy.model_dump()

    @classmethod
    def _has_explicit_path(cls, text: str) -> bool:
        if not text:
            return False

        # Check cloud paths BEFORE URL stripping (s3://, gs://, etc.)
        if cls._CLOUD_PATH_PATTERN.search(text):
            return True

        text_without_urls = cls._URL_PATTERN.sub(" ", text)
        return any(
            pattern.search(text_without_urls)
            for pattern in (
                cls._WINDOWS_PATH_PATTERN,
                cls._POSIX_PATH_PATTERN,
                cls._RELATIVE_FILE_PATTERN,
                cls._UNC_PATH_PATTERN,
            )
        )

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
