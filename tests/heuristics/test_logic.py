from app.models_v2 import IRv2, ConstraintV2
from app.heuristics.handlers.logic import LogicHandler


class MockIR:
    def __init__(self, text=""):
        self.metadata = {"original_text": text}


def test_resolve_conciseness_conflict():
    handler = LogicHandler()
    ir2 = IRv2(
        constraints=[
            ConstraintV2(text="Be concise", priority=10),
            ConstraintV2(text="Explain in extreme detail", priority=50),
        ]
    )
    ir1 = MockIR("Test prompt")

    handler.handle(ir2, ir1)

    # "Be concise" should be removed because "Explain in extreme detail" has higher priority
    texts = [c.text for c in ir2.constraints]
    assert "Explain in extreme detail" in texts
    assert "Be concise" not in texts

    # Check for diagnostic warning
    assert any("Conflict resolved" in d.message for d in ir2.diagnostics)
    assert any("removed 'be concise'" in d.message.lower() for d in ir2.diagnostics)


def test_resolve_format_conflict():
    handler = LogicHandler()
    ir2 = IRv2(
        constraints=[
            ConstraintV2(text="Output JSON", priority=100),
            ConstraintV2(text="Output Markdown table", priority=20),
        ]
    )
    ir1 = MockIR("Test prompt")

    handler.handle(ir2, ir1)

    # "Output Markdown table" should be removed
    texts = [c.text for c in ir2.constraints]
    assert "Output JSON" in texts
    assert "Output Markdown table" not in texts

    assert any("Conflict resolved" in d.message for d in ir2.diagnostics)


def test_inject_reasoning_for_math():
    handler = LogicHandler()
    ir2 = IRv2()
    # Mocking a math task prompt
    ir1 = MockIR("Calculate the eigenvalue of this matrix")

    handler.handle(ir2, ir1)

    # Should inject <thinking> constraint
    texts = [c.text for c in ir2.constraints]
    assert any("<thinking>" in t for t in texts)
    assert any(
        "priority" in str(c.priority) or c.priority >= 90
        for c in ir2.constraints
        if "<thinking>" in c.text
    )


def test_no_conflict_mixed_priorities():
    """Ensure non-conflicting constraints are kept even with different priorities."""
    handler = LogicHandler()
    ir2 = IRv2(
        constraints=[
            ConstraintV2(text="Use Python", priority=80),
            ConstraintV2(text="Be nice", priority=10),
        ]
    )
    ir1 = MockIR("Test prompt")

    handler.handle(ir2, ir1)

    texts = [c.text for c in ir2.constraints]
    assert "Use Python" in texts
    assert "Be nice" in texts
    assert len(ir2.diagnostics) == 0  # No conflict warnings
