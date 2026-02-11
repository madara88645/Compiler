import pytest
from app.heuristics.handlers.psycholinguist import PsycholinguistHandler
from app.models_v2 import IRv2
from app.models import IR


@pytest.fixture
def handler():
    return PsycholinguistHandler()


def test_urgency_detection(handler):
    text = "I need this fixed ASAP! It's critical."
    ir_v2 = IRv2(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )
    ir_v1 = IR(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.metadata["user_sentiment"] == "urgent"
    # Check constraint injection
    constraints = [c.text for c in ir_v2.constraints]
    assert "Prioritize brevity and actionable steps; avoid preamble." in constraints


def test_frustration_detection(handler):
    text = "Why is this error happening?? I don't understand! WTF"
    ir_v2 = IRv2(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Python Expert",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )
    ir_v1 = IR(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Python Expert",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.metadata["user_sentiment"] == "frustrated"
    # Check persona trait injection
    assert "Empathetic and patient teacher" in ir_v2.role
    assert "Python Expert" in ir_v2.role


def test_cultural_detection_uk(handler):
    text = "Check the colour of the centre element."
    ir_v2 = IRv2(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )
    ir_v1 = IR(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.metadata["cultural_context"] == "British"
    assert "(Use British English norms)" in ir_v2.role


def test_cultural_detection_us(handler):
    text = "Check the color of the center element."
    ir_v2 = IRv2(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )
    ir_v1 = IR(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.metadata["cultural_context"] == "American"
    assert "(Use American English norms)" in ir_v2.role


def test_neutral_sentiment(handler):
    text = "Write a function to calculate fibonacci."
    ir_v2 = IRv2(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        intents=[],
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )
    ir_v1 = IR(
        metadata={"original_text": text},
        language="en",
        persona="assistant",
        role="Assistant",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="text",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.metadata["user_sentiment"] == "neutral"
    # No extra constraints or role changes expected for neutral
    assert len(ir_v2.constraints) == 0
    assert ir_v2.role == "Assistant"
