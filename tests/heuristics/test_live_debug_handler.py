import pytest
from app.models import IR
from app.models_v2 import IRv2
from app.heuristics.handlers.debug import LiveDebugHandler


@pytest.fixture
def handler():
    return LiveDebugHandler()


def test_live_debug_happy_path(handler):
    # Happy path: metadata containing the `live_debug` flag
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"persona_evidence": {"flags": {"live_debug": True}}},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert "debug" in ir_v2.intents


def test_live_debug_negative_path_missing_persona_evidence(handler):
    # Negative path: metadata is missing `persona_evidence`
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert "debug" not in ir_v2.intents


def test_live_debug_negative_path_missing_flags(handler):
    # Negative path: metadata contains `persona_evidence` but is missing `flags`
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"persona_evidence": {}},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert "debug" not in ir_v2.intents


def test_live_debug_negative_path_missing_live_debug(handler):
    # Negative path: metadata contains `flags` but is missing `live_debug`
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"persona_evidence": {"flags": {}}},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert "debug" not in ir_v2.intents


def test_live_debug_negative_path_live_debug_false(handler):
    # Negative path: metadata contains `live_debug` but it is set to False
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"persona_evidence": {"flags": {"live_debug": False}}},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert "debug" not in ir_v2.intents
