import pytest

from app.heuristics.handlers.constraints import ConstraintHandler
from app.heuristics.logic_analyzer import (
    LogicAnalysisResult,
    NegativeConstraint,
    DependencyRule,
    MissingInfo,
    IOMapping,
)
from app.models import IR
from app.models_v2 import IRv2


@pytest.fixture
def handler():
    return ConstraintHandler()


def _ir(text: str = "", **metadata) -> IR:
    md = {"original_text": text}
    md.update(metadata)
    return IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        metadata=md,
    )


# --------------------------------------------------------------------------
# detect_negations
# --------------------------------------------------------------------------


def test_detect_negations_no_matches_returns_empty(handler):
    analysis = LogicAnalysisResult(negations=[])
    result = handler.detect_negations(analysis)
    assert result == []


def test_detect_negations_creates_restriction_constraint(handler):
    neg = NegativeConstraint(
        original_text="Do not use classes.",
        stripped_text="use classes.",
        negation_word="do not",
        anti_pattern="Instead: use classes.",
    )
    analysis = LogicAnalysisResult(negations=[neg])

    result = handler.detect_negations(analysis)

    assert len(result) == 1
    c = result[0]
    assert c.text == "❌ RESTRICTION: Do not use classes."
    assert c.origin == "restriction"
    assert c.priority == 85
    assert c.rationale == "Anti-pattern: Instead: use classes."
    # id is a deterministic hash of the original text
    assert c.id == handler._mk_id(neg.original_text)


def test_detect_negations_multiple_matches_preserve_order(handler):
    neg1 = NegativeConstraint("Never use eval.", "use eval.", "never", "Always consider: use eval.")
    neg2 = NegativeConstraint("Avoid globals.", "globals.", "avoid", "Prefer: globals.")
    analysis = LogicAnalysisResult(negations=[neg1, neg2])

    result = handler.detect_negations(analysis)

    assert len(result) == 2
    assert result[0].text == "❌ RESTRICTION: Never use eval."
    assert result[1].text == "❌ RESTRICTION: Avoid globals."
    # Different source text should yield different ids.
    assert result[0].id != result[1].id


# --------------------------------------------------------------------------
# detect_dependencies
# --------------------------------------------------------------------------


def test_detect_dependencies_no_matches_returns_empty(handler):
    analysis = LogicAnalysisResult(dependencies=[])
    assert handler.detect_dependencies(analysis) == []


@pytest.mark.parametrize(
    "dep_type,expected_label",
    [
        ("because", "Reason"),
        ("so_that", "Purpose"),
        ("in_order_to", "Goal"),
        ("if_then", "Condition"),
        ("result", "Result"),
        ("unknown_type", "Reason"),  # falls back to default label
    ],
)
def test_detect_dependencies_reason_label_mapping(handler, dep_type, expected_label):
    dep = DependencyRule(
        action="refactor the module",
        reason="it improves readability",
        full_text="refactor the module because it improves readability",
        dependency_type=dep_type,
    )
    analysis = LogicAnalysisResult(dependencies=[dep])

    result = handler.detect_dependencies(analysis)

    assert len(result) == 1
    c = result[0]
    assert c.text == "\U0001f4cb RULE: refactor the module"
    assert c.rationale == f"{expected_label}: it improves readability"
    assert c.origin == "dependency"
    assert c.priority == 75
    assert c.id == handler._mk_id(dep.full_text)


def test_detect_dependencies_multiple_preserve_order(handler):
    dep1 = DependencyRule("do X", "reason one", "full text one", "because")
    dep2 = DependencyRule("do Y", "reason two", "full text two", "so_that")
    analysis = LogicAnalysisResult(dependencies=[dep1, dep2])

    result = handler.detect_dependencies(analysis)

    assert [c.rationale for c in result] == ["Reason: reason one", "Purpose: reason two"]


# --------------------------------------------------------------------------
# _extract_io_constraints
# --------------------------------------------------------------------------


def test_extract_io_constraints_no_mappings_returns_empty(handler):
    analysis = LogicAnalysisResult(io_mappings=[])
    assert handler._extract_io_constraints(analysis) == []


def test_extract_io_constraints_skips_low_confidence(handler):
    io = IOMapping(
        input_type="text", process_action="process", output_format="json", confidence=0.2
    )
    analysis = LogicAnalysisResult(io_mappings=[io])

    assert handler._extract_io_constraints(analysis) == []


def test_extract_io_constraints_includes_at_or_above_threshold(handler):
    io = IOMapping(
        input_type="csv", process_action="analyze", output_format="table", confidence=0.3
    )
    analysis = LogicAnalysisResult(io_mappings=[io])

    result = handler._extract_io_constraints(analysis)

    assert len(result) == 1
    c = result[0]
    assert c.text == "\U0001f504 FLOW: Input(csv) → Process(analyze) → Output(table)"
    assert c.origin == "io_flow"
    assert c.priority == 50
    assert c.rationale == "Confidence: 30%"


def test_extract_io_constraints_multiple_mappings_get_unique_ids(handler):
    io1 = IOMapping(input_type="json", process_action="parse", output_format="text", confidence=0.9)
    io2 = IOMapping(input_type="json", process_action="parse", output_format="text", confidence=0.9)
    analysis = LogicAnalysisResult(io_mappings=[io1, io2])

    result = handler._extract_io_constraints(analysis)

    assert len(result) == 2
    assert result[0].id != result[1].id


# --------------------------------------------------------------------------
# _extract_diagnostics
# --------------------------------------------------------------------------


def test_extract_diagnostics_no_missing_info_returns_empty(handler):
    analysis = LogicAnalysisResult(missing_info=[])
    assert handler._extract_diagnostics(analysis) == []


def test_extract_diagnostics_maps_severity_and_builds_suggestion(handler):
    missing = MissingInfo(
        entity="database",
        context="...the database is...",
        placeholder="[MISSING: Database Schema]",
        severity="error",
    )
    analysis = LogicAnalysisResult(missing_info=[missing])

    result = handler._extract_diagnostics(analysis)

    assert len(result) == 1
    d = result[0]
    assert d.severity == "error"
    assert d.message == "Missing: database"
    assert d.suggestion == "Please provide Database Schema"
    assert d.category == "missing_info"


def test_extract_diagnostics_unknown_severity_defaults_to_warning(handler):
    missing = MissingInfo(
        entity="thing", context="ctx", placeholder="[MISSING: thing]", severity="totally_unknown"
    )
    analysis = LogicAnalysisResult(missing_info=[missing])

    result = handler._extract_diagnostics(analysis)

    assert result[0].severity == "warning"


def test_extract_diagnostics_adds_summary_when_more_than_three(handler):
    missing_items = [
        MissingInfo(entity=f"entity{i}", context="ctx", placeholder=f"[MISSING: entity{i}]")
        for i in range(4)
    ]
    analysis = LogicAnalysisResult(missing_info=missing_items)

    result = handler._extract_diagnostics(analysis)

    # 4 individual diagnostics + 1 summary diagnostic
    assert len(result) == 5
    summary = result[-1]
    assert summary.category == "completeness"
    assert "4 total" in summary.message


def test_extract_diagnostics_no_summary_when_three_or_fewer(handler):
    missing_items = [
        MissingInfo(entity=f"entity{i}", context="ctx", placeholder=f"[MISSING: entity{i}]")
        for i in range(3)
    ]
    analysis = LogicAnalysisResult(missing_info=missing_items)

    result = handler._extract_diagnostics(analysis)

    assert len(result) == 3
    assert all(d.category == "missing_info" for d in result)


# --------------------------------------------------------------------------
# handle() integration - exercises the above via a realistic prompt
# --------------------------------------------------------------------------


def test_handle_integrates_negations_dependencies_and_diagnostics(handler):
    text = (
        "Do not use global variables. "
        "Refactor the module because it improves readability. "
        "Please analyze the database and return a json report."
    )
    ir_v1 = _ir(text)
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    origins = {c.origin for c in ir_v2.constraints}
    assert "restriction" in origins
    assert "dependency" in origins
    assert "logic_analysis" in ir_v2.metadata
    assert ir_v2.metadata["logic_analysis"]["negation_count"] >= 1
    assert ir_v2.metadata["logic_analysis"]["dependency_count"] >= 1


def test_handle_without_original_text_only_converts_v1_constraints(handler):
    ir_v1 = IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=[],
        output_format="markdown",
        length_hint="medium",
        constraints=["Be concise"],
        metadata={},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert len(ir_v2.constraints) == 1
    assert ir_v2.constraints[0].text == "Be concise"
    assert "logic_analysis" not in ir_v2.metadata


def test_handle_deduplicates_constraints_by_id(handler):
    # IR's own field validator already dedupes ir_v1.constraints by lowercase
    # text, so to exercise ConstraintHandler's own id-based dedup we build the
    # IR via model_construct() to bypass that validator and force a genuine
    # duplicate through to handle().
    ir_v1 = IR.model_construct(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        inputs={},
        constraints=["Be concise", "Be concise"],
        style=[],
        tone=[],
        output_format="markdown",
        length_hint="medium",
        steps=[],
        examples=[],
        banned=[],
        tools=[],
        metadata={},
    )
    ir_v2 = IRv2()

    handler.handle(ir_v2, ir_v1)

    assert len(ir_v2.constraints) == 1
