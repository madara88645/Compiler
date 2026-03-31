import json

import pytest
from jsonschema import validate

from app.compiler import compile_text_v2
from app.resources import get_ir_schema_text


@pytest.mark.parametrize(
    ("prompt", "expected_intent"),
    [
        ("Write a creative launch post for my AI startup", "creative"),
        (
            "Explain async await like I'm a beginner and give a simple Python example",
            "explanation",
        ),
        ("Propose a pricing strategy for a student SaaS", "proposal"),
        ("Prepare me for a machine learning interview", "preparation"),
        ("Troubleshoot why my FastAPI app fails on Railway", "troubleshooting"),
    ],
)
def test_ir_v2_detects_high_value_intents(prompt, expected_intent):
    ir2 = compile_text_v2(prompt)

    assert expected_intent in ir2.intents


def test_ir_v2_code_review_keeps_multi_intent_context():
    ir2 = compile_text_v2("Review this auth code for security vulnerabilities")

    assert "code" in ir2.intents
    assert "review" in ir2.intents
    assert "risk" in ir2.intents


def test_ir_v2_debug_and_troubleshooting_prompt_validates_against_schema():
    schema = json.loads(get_ir_schema_text(v2=True))
    ir2 = compile_text_v2("Debug this Python traceback from my repo and troubleshoot the failure")

    validate(instance=ir2.model_dump(), schema=schema)
    assert "debug" in ir2.intents
    assert "troubleshooting" in ir2.intents
