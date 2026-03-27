import json
from jsonschema import validate
from app.compiler import compile_text_v2
from app.resources import get_ir_schema_text


def test_ir_v2_schema_teaching():
    ir2 = compile_text_v2("teach me binary search in 10 minutes beginner level")
    schema = json.loads(get_ir_schema_text(v2=True))
    validate(instance=ir2.model_dump(), schema=schema)
    assert "teaching" in ir2.intents
    assert any(c.origin.startswith("teaching") for c in ir2.constraints)
    # priorities assigned
    assert any(c.priority >= 55 for c in ir2.constraints)


def test_ir_v2_schema_general():
    ir2 = compile_text_v2("explain something completely unrelated to tech or finance")
    schema = json.loads(get_ir_schema_text(v2=True))
    validate(instance=ir2.model_dump(), schema=schema)
    # domain confidence may be None in metadata; ensure v2 carries heuristic2_version
    assert ir2.metadata.get("heuristic2_version") is not None
