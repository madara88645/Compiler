from app.compiler import compile_text
from app.heuristics.handlers.domain_expert import DomainHandler
from app.models_v2 import IRv2
from app.models import IR


def test_domain_confidence_ratio_basic():
    text = "aws serverless lambda docker kubernetes python"
    ir = compile_text(text)
    md = ir.metadata
    # Expect cloud or software domain; evidence for both
    scores = md.get("domain_scores") or {}
    assert scores
    if ir.domain != "general":
        assert ir.metadata.get("domain_confidence") is not None
        conf = ir.metadata["domain_confidence"]
        assert 0 < conf <= 1
        # Primary domain count should be max
        primary_count = scores.get(ir.domain, 0)
        assert primary_count == max(scores.values())


def test_domain_confidence_none_for_general():
    ir = compile_text("explain something completely unrelated to tech or finance")
    if ir.domain == "general":
        assert ir.metadata.get("domain_confidence") is None


def test_domain_confidence_ratio_single_domain_full():
    ir = compile_text("python python python api microservice docker")
    if ir.domain != "general":
        # If only one domain present, confidence should be 1.0
        scores = ir.metadata.get("domain_scores") or {}
        if len(scores) == 1:
            assert abs(ir.metadata.get("domain_confidence") - 1.0) < 1e-9


def test_implied_persona_detection():
    # Test text implying Python Developer
    text = "def calculate_sum(a, b): return a + b"

    handler = DomainHandler()

    # Create a dummy IRv2 with generic persona
    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="",
        domain="coding",
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
        metadata={"original_text": text},
    )
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="",
        domain="coding",
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
        metadata={"original_text": text},
    )

    handler.handle(ir_v2, ir_v1)

    # Should have updated persona
    assert ir_v2.persona == "expert"
    assert "Python Developer" in ir_v2.role
    assert ir_v2.metadata.get("implied_persona")
    assert ir_v2.metadata["implied_persona"]["persona"] == "Python Developer"


def test_implied_persona_sql():
    text = "select * from users where id = 1"

    handler = DomainHandler()
    ir_v2 = IRv2(
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
        metadata={"original_text": text},
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
    assert "Database Administrator" in ir_v2.role
