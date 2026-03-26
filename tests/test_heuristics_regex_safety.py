import time

from app.heuristics import extract_comparison_items, extract_inputs
from app.heuristics.handlers.structure import StructureHandler


def test_extract_inputs_budget_pathological_spacing_stays_fast():
    text = "budget 0-" + (" " * 5000)

    started = time.perf_counter()
    result = extract_inputs(text, "en")
    elapsed = time.perf_counter() - started

    assert result["budget"] == "0"
    assert elapsed < 0.2


def test_infer_schema_pathological_parentheses_stays_fast():
    handler = StructureHandler()
    text = "Extract fields: name (string), age " + ("(" * 10000)

    started = time.perf_counter()
    schema = handler.infer_schema(text)
    elapsed = time.perf_counter() - started

    assert schema
    assert elapsed < 0.15


def test_inject_variables_preserves_existing_placeholders():
    handler = StructureHandler()

    text, variables = handler._inject_variables("{{TEST_VAR}} TEST_VAR and API")

    assert text == "{{TEST_VAR}} {{TEST_VAR}} and API"
    assert variables == ["TEST_VAR"]


def test_extract_comparison_items_handles_turkish_compare_form():
    assert extract_comparison_items("React ile Vue kar\u015f\u0131la\u015ft\u0131r") == [
        "react",
        "vue",
    ]
