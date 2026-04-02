import json
from jsonschema import validate
from app.compiler import compile_text
from app.resources import get_ir_schema_text

schema = json.loads(get_ir_schema_text(v2=False))
schema_v2 = json.loads(get_ir_schema_text(v2=True))


def test_schema_validation():
    ir = compile_text("Summarize recent stock market trends in a concise table")
    validate(instance=ir.model_dump(), schema=schema)


def test_v1_schema_accepts_developer_persona_for_code_requests():
    ir = compile_text("Implement a Python URL parser with tests and edge cases")

    assert ir.persona == "developer"
    validate(instance=ir.model_dump(), schema=schema)


def test_v1_and_v2_persona_enums_stay_aligned_for_shared_values():
    v1_personas = set(schema["properties"]["persona"]["enum"])
    v2_personas = set(schema_v2["properties"]["persona"]["enum"])

    assert v1_personas == v2_personas
