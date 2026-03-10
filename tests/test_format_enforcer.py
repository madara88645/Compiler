from app.heuristics.handlers.format_enforcer import FormatEnforcerHandler
from app.models import IR
from app.models_v2 import IRv2


def test_format_enforcer_injects_constraint():
    handler = FormatEnforcerHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="markdown",
        length_hint="short",
    )

    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        metadata={"original_text": "Extract the emails into a JSON file"},
    )

    handler.handle(ir_v2, ir_v1)

    assert any("No conversational filler" in c for c in ir_v1.constraints)
    assert any("No conversational filler" in c.text for c in ir_v2.constraints)
