import json
from pathlib import Path
from jsonschema import validate
from app.compiler import compile_text_v2

def test_ir_v2_schema_teaching():
    ir2 = compile_text_v2("teach me binary search in 10 minutes beginner level")
    schema = json.loads(Path('schema/ir_v2.schema.json').read_text(encoding='utf-8'))
    validate(instance=ir2.model_dump(), schema=schema)
    assert 'teaching' in ir2.intents
    assert any(c.origin.startswith('teaching') for c in ir2.constraints)
    # priorities assigned
    assert any(c.priority >= 55 for c in ir2.constraints)


def test_ir_v2_schema_general():
    ir2 = compile_text_v2("explain something completely unrelated to tech or finance")
    schema = json.loads(Path('schema/ir_v2.schema.json').read_text(encoding='utf-8'))
    validate(instance=ir2.model_dump(), schema=schema)
    # domain confidence may be None in metadata; ensure v2 carries heuristic2_version
    assert ir2.metadata.get('heuristic2_version') is not None
