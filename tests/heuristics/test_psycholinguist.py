import pytest
from app.heuristics.handlers.psycholinguist import PsycholinguistHandler, detect_ambiguity
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


def test_ambiguity_detection_clean():
    """Test that clear text triggers no ambiguity."""
    text = "Write a function to calculate fibonacci."
    result = detect_ambiguity(text)
    assert result.is_ambiguous is False
    assert len(result.ambiguous_terms) == 0
    assert len(result.suggestions) == 0


def test_ambiguity_detection_fix_it():
    """Test 'fix_it' pattern detection."""
    texts = [
        "Please fix it now.",
        "It is broken.",
        "Can you help me?",
        "It doesn't work as expected."
    ]
    for text in texts:
        result = detect_ambiguity(text)
        assert result.is_ambiguous is True
        assert "fix_it" in result.ambiguous_terms
        assert any("Specify *what* is broken" in s for s in result.suggestions)


def test_ambiguity_detection_better():
    """Test 'better' pattern detection."""
    texts = [
        "Make it better.",
        "How can I improve it?",
        "Please enhance this function."
    ]
    for text in texts:
        result = detect_ambiguity(text)
        assert result.is_ambiguous is True
        assert "better" in result.ambiguous_terms
        assert any("Define 'better'" in s for s in result.suggestions)


def test_ambiguity_detection_clean_up():
    """Test 'clean_up' pattern detection."""
    texts = [
        "I need to clean up this module.",
        "Refactor this mess.",
        "Optimize the performance."
    ]
    for text in texts:
        result = detect_ambiguity(text)
        assert result.is_ambiguous is True
        assert "clean_up" in result.ambiguous_terms
        assert any("Specify the goal" in s for s in result.suggestions)


def test_ambiguity_detection_stuff():
    """Test 'stuff' pattern detection."""
    texts = [
        "Do some stuff with this.",
        "There are too many things here.",
        "Write something useful."
    ]
    for text in texts:
        result = detect_ambiguity(text)
        assert result.is_ambiguous is True
        assert "stuff" in result.ambiguous_terms
        assert any("Replace vague words" in s for s in result.suggestions)


def test_ambiguity_detection_multiple():
    """Test detection of multiple ambiguous patterns."""
    text = "Fix it and make it better."
    result = detect_ambiguity(text)
    assert result.is_ambiguous is True
    assert "fix_it" in result.ambiguous_terms
    assert "better" in result.ambiguous_terms
    assert len(result.suggestions) >= 2


def test_ambiguity_detection_case_insensitive():
    """Test case insensitivity."""
    text = "PLEASE FIX THIS STUFF"
    result = detect_ambiguity(text)
    assert result.is_ambiguous is True
    assert "fix_it" in result.ambiguous_terms
    assert "stuff" in result.ambiguous_terms
