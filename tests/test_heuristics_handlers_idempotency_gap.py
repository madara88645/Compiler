"""Coverage gap: FormatEnforcerHandler.handle() and ParadoxResolverHandler.handle()
both guard against double-inserting the same constraint into ir_v1.constraints
and ir_v2.constraints. Calling .handle() twice on the same IR should not
duplicate the injected constraint.
"""
from app.heuristics.handlers.format_enforcer import FormatEnforcerHandler
from app.heuristics.handlers.paradox_resolver import ParadoxResolverHandler
from app.models import IR
from app.models_v2 import IRv2


def test_format_enforcer_handle_twice_does_not_duplicate_constraint():
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
    handler.handle(ir_v2, ir_v1)

    v1_matches = [c for c in ir_v1.constraints if "No conversational filler" in c]
    v2_matches = [c for c in ir_v2.constraints if "No conversational filler" in c.text]

    assert len(v1_matches) == 1
    assert len(v2_matches) == 1


def test_paradox_resolver_handle_twice_does_not_duplicate_constraint():
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
    handler.handle(ir_v2, ir_v1)

    v1_matches = [c for c in ir_v1.constraints if "CONFLICT DETECTED" in c]
    v2_matches = [c for c in ir_v2.constraints if "CONFLICT DETECTED" in c.text]

    assert len(v1_matches) == 1
    assert len(v2_matches) == 1
