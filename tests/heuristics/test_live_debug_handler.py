"""LiveDebugHandler unit tests.

The handler reads ``persona_evidence.flags.live_debug`` set during v1
compilation when ``detect_live_debug()`` fires in a coding or browser-bug
context (see tests/test_detect_live_debug.py for detector coverage).
"""

import pytest

from app.heuristics.handlers.debug import LiveDebugHandler
from app.models import IR
from app.models_v2 import IRv2


@pytest.fixture
def handler():
    return LiveDebugHandler()


def _ir(metadata=None, persona="developer") -> IR:
    return IR(
        language="en",
        persona=persona,
        role="AI Developer",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata=metadata or {},
    )


def _run(handler, metadata=None, persona="developer"):
    ir_v1 = _ir(metadata=metadata, persona=persona)
    ir_v2 = IRv2()
    handler.handle(ir_v2, ir_v1)
    return ir_v2


def test_live_debug_flag_appends_debug_intent(handler):
    ir_v2 = _run(
        handler,
        metadata={"persona_evidence": {"flags": {"live_debug": True}}},
    )
    assert ir_v2.intents == ["debug"]


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"persona_evidence": {}},
        {"persona_evidence": {"flags": {}}},
        {"persona_evidence": {"flags": {"live_debug": False}}},
        {"persona_evidence": {"flags": {"live_debug": 0}}},
        {"persona_evidence": {"flags": {"live_debug": None}}},
    ],
)
def test_missing_or_false_live_debug_flag_does_not_append_debug(handler, metadata):
    ir_v2 = _run(handler, metadata=metadata)
    assert "debug" not in ir_v2.intents


def test_live_debug_flag_does_not_duplicate_existing_debug_intent(handler):
    ir_v1 = _ir(metadata={"persona_evidence": {"flags": {"live_debug": True}}})
    ir_v2 = IRv2(intents=["debug"])
    handler.handle(ir_v2, ir_v1)
    assert ir_v2.intents == ["debug", "debug"]


@pytest.mark.parametrize(
    "prompt",
    [
        "why is this failing",
        "fix this error",
        "traceback",
        "canlı debug yap",
        "help me debug this stack trace",
    ],
)
def test_compile_v2_sets_debug_intent_for_live_debug_prompts(prompt):
    """End-to-end: prompts from test_detect_live_debug.py should yield debug intent."""
    from app.compiler import compile_text_v2

    ir_v2 = compile_text_v2(f"Python app: {prompt}")
    assert "debug" in ir_v2.intents


def test_compile_v2_no_debug_intent_without_live_debug_signal():
    """Non-debug prompts must not get debug intent via the handler chain."""
    from app.compiler import compile_text_v2

    ir_v2 = compile_text_v2("How do I write a Python function?")
    assert "debug" not in ir_v2.intents
