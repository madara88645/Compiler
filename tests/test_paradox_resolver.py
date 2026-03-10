from app.heuristics.handlers.paradox_resolver import ParadoxResolverHandler
from app.models import IR
from app.models_v2 import IRv2


def test_paradox_resolver_detects_length_conflict():
    handler = ParadoxResolverHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="markdown",
        length_hint="short",
        constraints=["be brief", "be very detailed"],
    )

    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        metadata={"original_text": "Make it very short but also explain everything in detail"},
    )

    handler.handle(ir_v2, ir_v1)

    assert any("CONFLICT DETECTED" in c for c in ir_v1.constraints)
    assert any("CONFLICT DETECTED" in c.text for c in ir_v2.constraints)
