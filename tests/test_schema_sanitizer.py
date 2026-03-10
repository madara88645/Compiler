from app.heuristics.handlers.schema_sanitizer import SchemaSanitizerHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


def test_schema_sanitizer_fixes_data_types():
    handler = SchemaSanitizerHandler()

    schema_text = """Strictly follow this JSON Schema:
```json
{
  "type": "object",
  "properties": {
    "phone_number": {
      "type": "integer"
    },
    "zip_code": {
      "type": "number"
    },
    "age": {
      "type": "integer"
    }
  }
}
```"""

    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="json",
        length_hint="short",
    )
    ir_v2 = IRv2(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        constraints=[ConstraintV2(type="formatting", text=schema_text)],
    )

    handler.handle(ir_v2, ir_v1)

    sanitized_text = ir_v2.constraints[0].text

    # Phone number and zip code should be forced to string
    assert '"phone_number": {\n      "type": "string"' in sanitized_text
    assert '"zip_code": {\n      "type": "string"' in sanitized_text
    # Age should remain integer
    assert '"age": {\n      "type": "integer"' in sanitized_text
