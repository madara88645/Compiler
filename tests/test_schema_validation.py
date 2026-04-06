import json
from jsonschema import validate
from app.compiler import compile_text
from app.ir_contract import (
    IR_CONSTRAINT_PRIORITIES,
    IR_DATA_SENSITIVITY_LEVELS,
    IR_EXECUTION_MODES,
    IR_INTENTS,
    IR_LANGUAGES,
    IR_LENGTH_HINTS,
    IR_OUTPUT_FORMATS,
    IR_PERSONAS,
    IR_RISK_LEVELS,
    IR_STEP_TYPES,
)
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


def test_checked_in_schemas_match_shared_ir_contract_enums():
    assert set(schema["properties"]["language"]["enum"]) == set(IR_LANGUAGES)
    assert set(schema["properties"]["persona"]["enum"]) == set(IR_PERSONAS)
    assert set(schema["properties"]["output_format"]["enum"]) == set(IR_OUTPUT_FORMATS)
    assert set(schema["properties"]["length_hint"]["enum"]) == set(IR_LENGTH_HINTS)

    assert set(schema_v2["properties"]["language"]["enum"]) == set(IR_LANGUAGES)
    assert set(schema_v2["properties"]["persona"]["enum"]) == set(IR_PERSONAS)
    assert set(schema_v2["properties"]["output_format"]["enum"]) == set(IR_OUTPUT_FORMATS)
    assert set(schema_v2["properties"]["length_hint"]["enum"]) == set(IR_LENGTH_HINTS)
    assert set(schema_v2["properties"]["intents"]["items"]["enum"]) == set(IR_INTENTS)
    assert set(schema_v2["properties"]["steps"]["items"]["properties"]["type"]["enum"]) == set(IR_STEP_TYPES)
    assert (
        set(schema_v2["properties"]["constraints"]["items"]["properties"]["priority"]["enum"])
        == set(IR_CONSTRAINT_PRIORITIES)
    )

    policy = schema_v2["properties"]["policy"]["properties"]
    assert set(policy["risk_level"]["enum"]) == set(IR_RISK_LEVELS)
    assert set(policy["data_sensitivity"]["enum"]) == set(IR_DATA_SENSITIVITY_LEVELS)
    assert set(policy["execution_mode"]["enum"]) == set(IR_EXECUTION_MODES)


def test_shared_ir_intents_cover_high_value_v2_heuristic_outputs():
    expected_v2_intents = {
        "summary",
        "compare",
        "variants",
        "recency",
        "risk",
        "code",
        "ambiguous",
        "creative",
        "explanation",
        "proposal",
        "review",
        "preparation",
        "troubleshooting",
        "debug",
        "capability_mismatch",
        "decompose",
        "summarize",
        "teaching",
    }

    assert expected_v2_intents.issubset(set(IR_INTENTS))
