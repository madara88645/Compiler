import sys
import os

sys.path.append(os.getcwd())

from app.heuristics.security import scan_text  # noqa: E402


def test_no_secrets():
    text = "Hello world, this is a safe text."
    result = scan_text(text)
    assert result.is_safe is True
    assert result.redacted_text == text
    assert len(result.findings) == 0


def test_api_key_openai():
    text = "My key is sk-1234567890abcdef1234567890abcdef1234567890abcdef."
    result = scan_text(text)
    assert result.is_safe is False
    assert "[OPENAI_KEY_REDACTED]" in result.redacted_text
    assert "sk-" not in result.redacted_text
    assert len(result.findings) == 1
    assert result.findings[0]["type"] == "openai_key"


def test_email_redaction():
    text = "Contact me at user@example.com for more info."
    result = scan_text(text)
    assert result.is_safe is False
    assert "[EMAIL_REDACTED]" in result.redacted_text
    assert "user@example.com" not in result.redacted_text


def test_ipv4_redaction():
    text = "Server is at 192.168.1.100."
    result = scan_text(text)
    assert result.is_safe is False
    assert "[IPV4_REDACTED]" in result.redacted_text
    assert "192.168.1.100" not in result.redacted_text


def test_ipv4_allowlist():
    text = "Localhost is 127.0.0.1."
    result = scan_text(text)
    assert result.is_safe is True
    assert "127.0.0.1" in result.redacted_text


def test_generic_api_key():
    text = "api_key = 'abcdef1234567890abcdef12345'"
    result = scan_text(text)
    assert result.is_safe is False
    assert "[GENERIC_API_KEY_REDACTED]" in result.redacted_text
    assert "abcdef1234567890abcdef12345" not in result.redacted_text


def test_multiple_findings():
    text = "Key: sk-1234567890abcdef1234567890abcdef1234567890abcdef and email: test@test.com"
    result = scan_text(text)
    assert result.is_safe is False
    assert len(result.findings) == 2
    assert "[OPENAI_KEY_REDACTED]" in result.redacted_text
    assert "[EMAIL_REDACTED]" in result.redacted_text
