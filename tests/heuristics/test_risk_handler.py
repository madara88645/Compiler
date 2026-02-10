import pytest
from app.models import IR
from app.models_v2 import IRv2
from app.heuristics.handlers.risk import RiskHandler


@pytest.fixture
def risk_handler():
    return RiskHandler()


def test_real_time_capability_mismatch(risk_handler):
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=["Get news"],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"original_text": "What is the latest news today?"},
    )
    ir_v2 = IRv2()

    risk_handler.handle(ir_v2, ir_v1)

    diagnostics = ir_v2.diagnostics
    assert len(diagnostics) > 0
    assert any("not have real-time capabilities" in d.message for d in diagnostics)
    assert any(d.category == "capability" for d in diagnostics)


def test_image_generation_capability_mismatch(risk_handler):
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=["Draw image"],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"original_text": "Please generate an image of a cat."},
    )
    ir_v2 = IRv2()

    risk_handler.handle(ir_v2, ir_v1)

    diagnostics = ir_v2.diagnostics
    assert len(diagnostics) > 0
    assert any("text-only" in d.message for d in diagnostics)
    assert any(d.category == "capability" for d in diagnostics)


def test_no_capability_mismatch(risk_handler):
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=["Write poem"],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata={"original_text": "Write a poem about nature."},
    )
    ir_v2 = IRv2()

    risk_handler.handle(ir_v2, ir_v1)

    # specific risk flags might trigger standard warnings, but NOT capability warnings
    diagnostics = [d for d in ir_v2.diagnostics if d.category == "capability"]
    assert len(diagnostics) == 0
