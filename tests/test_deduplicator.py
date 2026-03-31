from app.heuristics.handlers.deduplicator import DeduplicatorHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


def test_deduplicator_removes_redundant_constraints():
    handler = DeduplicatorHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="json",
        length_hint="short",
        constraints=[
            "Output strict JSON. Do not output conversational text.",
            "No conversational filler. Return ONLY the requested format.",
            "Something else entirely.",
        ],
    )

    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        constraints=[
            ConstraintV2(
                type="formatting", text="Output strict JSON. Do not output conversational text."
            ),
            ConstraintV2(
                type="formatting",
                text="No conversational filler. Return ONLY the requested format.",
            ),
            ConstraintV2(type="general", text="Something else entirely."),
        ],
    )

    handler.handle(ir_v2, ir_v1)

    # "No conversational filler..." should be removed because it's redundant with "Output strict JSON..."
    v1_texts = " ".join(ir_v1.constraints)
    v2_texts = " ".join([c.text for c in ir_v2.constraints])

    assert "Output strict JSON" in v1_texts
    assert "No conversational filler" not in v1_texts
    assert "Output strict JSON" in v2_texts
    assert "No conversational filler" not in v2_texts


def test_deduplicator_removes_duplicate_intents_preserving_order():
    handler = DeduplicatorHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="markdown",
        length_hint="medium",
    )

    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        intents=["code", "review", "code", "risk", "review"],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.intents == ["code", "review", "risk"]


def test_deduplicator_normalizes_intents_while_deduping():
    handler = DeduplicatorHandler()

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="markdown",
        length_hint="medium",
    )

    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        intents=[" Code ", "review", "code", " REVIEW "],
    )

    handler.handle(ir_v2, ir_v1)

    assert ir_v2.intents == ["code", "review"]
