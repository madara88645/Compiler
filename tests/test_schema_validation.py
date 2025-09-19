import json
from jsonschema import validate
from pathlib import Path
from app.compiler import compile_text

schema = json.loads(Path("schema/ir.schema.json").read_text(encoding="utf-8"))


def test_schema_validation():
    ir = compile_text("Summarize recent stock market trends in a concise table")
    validate(instance=ir.model_dump(), schema=schema)
