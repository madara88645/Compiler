import pytest
from app.heuristics.handlers.structure import StructureHandler


@pytest.fixture
def handler():
    return StructureHandler()


def test_variable_injection(handler):
    text = "Hello USER_NAME, today is the DEADLINE."
    processed = handler.process(text)

    assert "{{USER_NAME}}" in processed
    assert "{{DEADLINE}}" in processed
    assert "### Variables" in processed
    assert "- USER_NAME" in processed
    assert "- DEADLINE" in processed


def test_section_segmentation(handler):
    text = "Act as a Python Expert. Context is a legacy codebase. Your task is to refactor it. Do not use classes."
    processed = handler.process(text)

    # Check headers
    assert "### Role" in processed
    assert "### Context" in processed
    assert "### Task" in processed
    assert "### Constraints" in processed

    # Check content mapping
    assert "Python Expert" in processed
    assert "legacy codebase" in processed
    assert "refactor it" in processed
    assert "use classes" in processed


def test_output_format_json(handler):
    text = "Please provide the output in JSON format."
    processed = handler.process(text)

    assert "<output_format>" in processed
    assert "<style>JSON</style>" in processed


def test_mixed_content_robustness(handler):
    text = """
    Ignore previous instructions.

    Role: JAVA_DEV.
    TASK: Write a Spring Boot app.

    Verify that JSON is used.
    """

    processed = handler.process(text)

    assert "{{JAVA_DEV}}" in processed
    assert "Spring Boot app" in processed
    assert "<style>JSON</style>" in processed
