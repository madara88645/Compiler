import pytest
from app.heuristics.handlers.safety import SafetyHandler
from app.models_v2 import IRv2


@pytest.fixture
def handler():
    return SafetyHandler()


def test_pii_email(handler):
    text = "Contact me at test@example.com for details."
    findings = handler._scan_pii(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Email Address"


def test_pii_phone(handler):
    text = "Call +1-555-012-3456 immediately."
    findings = handler._scan_pii(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Phone Number"


def test_pii_credit_card(handler):
    text = "My card is 4111 1111 1111 1111."
    findings = handler._scan_pii(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Credit Card Number"


def test_unsafe_keywords(handler):
    text = "How to bypass the filter and ignore previous instructions?"
    flags = handler._scan_unsafe_content(text)
    assert "bypass" in flags
    assert "ignore previous instructions" in flags


def test_guardrails_length_short(handler):
    text = "Hi"
    diag = handler._check_guardrails(text)
    assert diag is not None
    assert diag.message == "Prompt is extremely short"


def test_guardrails_length_long(handler):
    text = "A" * 20001
    diag = handler._check_guardrails(text)
    assert diag is not None
    assert "very long" in diag.message


def test_handler_integration():
    handler = SafetyHandler()
    ir2 = IRv2(
        language="en",
        persona="assistant",
        role="helper",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="markdown",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
        metadata={"original_text": "Call me at 555-123-4567"},
    )
    # Mock IR1
    from app.models import IR

    ir1 = IR(
        language="en",
        persona="assistant",
        role="helper",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="markdown",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir2, ir1)

    assert len(ir2.diagnostics) >= 1
    assert "Phone Number" in ir2.diagnostics[0].message
