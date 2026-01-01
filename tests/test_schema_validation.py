import json
from jsonschema import validate
from app.compiler import compile_text
from app.resources import get_ir_schema_text

schema = json.loads(get_ir_schema_text(v2=False))


def test_schema_validation():
    ir = compile_text("Summarize recent stock market trends in a concise table")
    validate(instance=ir.model_dump(), schema=schema)
