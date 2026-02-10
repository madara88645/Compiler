import pytest
from app.models import IR
from app.models_v2 import IRv2
from app.heuristics.handlers.structure import StructureHandler


@pytest.fixture
def handler():
    return StructureHandler()


@pytest.fixture
def ir_v2():
    return IRv2(
        language="en",
        persona="assistant",
        role="helper",
        domain="general",
        intents=[],
        goals=[],
        tasks=["Output strict JSON format."],
        inputs={},
        constraints=[],
        style=[],
        tone=[],
        output_format="",
        length_hint="",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
        metadata={"original_text": "Please provide the data in JSON format."},
    )


@pytest.fixture
def ir_v1():
    return IR(
        language="en",
        persona="assistant",
        role="helper",
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
        metadata={},
    )


def test_structure_handler_detects_json(handler, ir_v2, ir_v1):
    handler.handle(ir_v2, ir_v1)

    constraint = next((c for c in ir_v2.constraints if c.origin == "structure_handler"), None)
    assert constraint is not None
    assert "JSON" in constraint.text
    assert constraint.id == "structure_strict_json"


def test_structure_handler_detects_csv(handler, ir_v2, ir_v1):
    ir_v2.metadata["original_text"] = "I need the output as a CSV file."
    handler.handle(ir_v2, ir_v1)

    constraint = next((c for c in ir_v2.constraints if c.origin == "structure_handler"), None)
    assert constraint is not None
    assert "CSV" in constraint.text
    assert constraint.id == "structure_strict_csv"


def test_structure_handler_detects_xml(handler, ir_v2, ir_v1):
    ir_v2.metadata["original_text"] = "Please use XML format."
    handler.handle(ir_v2, ir_v1)

    constraint = next((c for c in ir_v2.constraints if c.origin == "structure_handler"), None)
    assert constraint is not None
    assert "XML" in constraint.text
    assert constraint.id == "structure_strict_xml"


def test_structure_handler_no_detection(handler, ir_v2, ir_v1):
    ir_v2.metadata["original_text"] = "Just tell me a story."
    handler.handle(ir_v2, ir_v1)

    constraint = next((c for c in ir_v2.constraints if c.origin == "structure_handler"), None)
    assert constraint is None


def test_structure_handler_process_method_unchanged(handler):
    # Verify the legacy process method still works
    text = "Extract name, email from user."
    structured = handler.process(text)
    assert "### Task" in structured
