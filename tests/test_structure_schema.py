import pytest
import json
from app.heuristics.handlers.structure import StructureHandler
from app.compiler import compile_text_v2


@pytest.fixture
def handler():
    return StructureHandler()


def test_infer_schema_basic(handler):
    text = "Extract name, email, and age from the user profile."
    schema_json = handler.infer_schema(text)
    assert schema_json

    schema = json.loads(schema_json)
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert "email" in schema["properties"]
    assert "age" in schema["properties"]

    # Type inference checks
    assert schema["properties"]["age"]["type"] == "integer"
    assert schema["properties"]["email"]["type"] == "string"


def test_infer_schema_explicit_fields_colon(handler):
    text = "Fields: title, body, tags (array), is_published"
    schema_json = handler.infer_schema(text)
    assert schema_json

    schema = json.loads(schema_json)
    assert "title" in schema["properties"]
    assert "tags" in schema["properties"]
    assert "is_published" in schema["properties"]

    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["properties"]["is_published"]["type"] == "boolean"


def test_infer_schema_no_intent(handler):
    text = "Write a python script to calculate pi."
    schema_json = handler.infer_schema(text)
    assert schema_json == ""


def test_compiler_integration():
    text = "Extract product_name, price, and stock_count."
    ir = compile_text_v2(text)

    # Check if constraint was added
    schema_constraint = next((c for c in ir.constraints if c.id == "schema_enforcement"), None)
    assert schema_constraint is not None
    assert "json" in schema_constraint.text.lower()
    assert "product_name" in schema_constraint.text

    # Check diagnostics
    diag = next((d for d in ir.diagnostics if d.category == "structure"), None)
    assert diag is not None
    assert "Auto-generated JSON Schema" in diag.message
