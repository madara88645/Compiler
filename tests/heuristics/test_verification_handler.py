import pytest

from app.compiler import compile_text_v2
from app.emitters import emit_system_prompt_v2
from app.heuristics.handlers.verification import (
    MIN_ITEMS,
    VerificationHandler,
    render_verification_block,
)
from app.models import IR
from app.models_v2 import ConstraintV2, IRv2


@pytest.fixture
def handler():
    return VerificationHandler()


def _ir_v1() -> IR:
    return IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        output_format="markdown",
        length_hint="medium",
    )


def _ir_v2(*constraints: ConstraintV2, language: str = "en") -> IRv2:
    return IRv2(language=language, constraints=list(constraints))


def _c(
    text: str, *, origin: str = "restriction", priority: int = 85, cid: str = ""
) -> ConstraintV2:
    return ConstraintV2(id=cid, text=text, origin=origin, priority=priority)


# --------------------------------------------------------------------------
# CHECKLIST CONSTRUCTION
# --------------------------------------------------------------------------


def test_checklist_lists_each_hard_requirement(handler):
    ir2 = _ir_v2(
        _c("Do not: add new dependencies.", origin="heuristic:logic_negation", priority=90),
        _c("❌ RESTRICTION: Exclude soft-deleted rows."),
        _c("Output strict JSON.", origin="structure_handler"),
    )

    handler.handle(ir2, _ir_v1())

    checklist = ir2.metadata["verification_checklist"]
    assert len(checklist) == 3
    assert "Do not: add new dependencies." in checklist
    # The display decoration is stripped so lines read uniformly.
    assert "Exclude soft-deleted rows." in checklist
    assert "Output strict JSON." in checklist


def test_checklist_covers_requirements_that_key_constraints_drops(handler):
    """emit_system_prompt_v2 renders only the top 3 constraints; the rest are lost."""
    ir2 = _ir_v2(
        _c("Never: log request bodies.", origin="heuristic:logic_negation", priority=90),
        _c("Exclude: soft-deleted rows.", origin="heuristic:logic_negation", priority=90),
        _c("Do not: add new dependencies.", origin="heuristic:logic_negation", priority=90),
        _c("❌ RESTRICTION: The response must not expose user emails."),
    )

    handler.handle(ir2, _ir_v1())

    checklist = ir2.metadata["verification_checklist"]
    assert any("expose user emails" in item for item in checklist)


def test_contained_duplicates_collapse_into_the_fuller_sentence(handler):
    """The compiler records a scoped clause and the user's whole sentence."""
    ir2 = _ir_v2(
        _c("Never: log request bodies.", origin="heuristic:logic_negation", priority=90),
        _c(
            "❌ RESTRICTION: It must not expose user emails and should never log request bodies.",
        ),
        _c("Do not: add new dependencies.", origin="heuristic:logic_negation", priority=90),
    )

    handler.handle(ir2, _ir_v1())

    checklist = ir2.metadata["verification_checklist"]
    # The pair collapses to a single line — the one that still mentions both
    # halves — leaving it plus the unrelated dependency requirement.
    assert len(checklist) == 2
    combined = next(item for item in checklist if "expose user emails" in item)
    assert "log request bodies" in combined
    assert sum("log request bodies" in item for item in checklist) == 1


def test_collapsing_below_the_minimum_stays_silent(handler):
    """Two records of one requirement are still just one requirement."""
    ir2 = _ir_v2(
        _c("Never: log request bodies.", origin="heuristic:logic_negation", priority=90),
        _c("❌ RESTRICTION: It should never log request bodies."),
    )

    handler.handle(ir2, _ir_v1())

    assert "verification_checklist" not in ir2.metadata


def test_advisory_and_non_checkable_constraints_are_excluded(handler):
    ir2 = _ir_v2(
        _c("Do not: add new dependencies.", origin="heuristic:logic_negation", priority=90),
        _c("❌ RESTRICTION: Exclude soft-deleted rows."),
        # Clarification request, not something an answer can be checked against.
        _c("Clarify ambiguous terms: fast", origin="ambiguous_terms", priority=30),
        # A description of the data flow, not a requirement.
        _c("🔄 FLOW: Input(csv) → Process(process) → Output(json)", origin="io_flow", priority=50),
    )

    handler.handle(ir2, _ir_v1())

    checklist = ir2.metadata["verification_checklist"]
    assert not any("Clarify ambiguous" in item for item in checklist)
    assert not any("FLOW" in item for item in checklist)


def test_json_schema_constraint_is_not_inlined(handler):
    """The schema block is already surfaced as [JSON Schema Enforced]."""
    ir2 = _ir_v2(
        _c("Do not: add new dependencies.", origin="heuristic:logic_negation", priority=90),
        _c("❌ RESTRICTION: Exclude soft-deleted rows."),
        _c(
            'Strictly follow this JSON Schema:\n```json\n{"type": "object"}\n```',
            origin="structure_handler",
            priority=90,
            cid="schema_enforcement",
        ),
    )

    handler.handle(ir2, _ir_v1())

    assert not any("```" in item for item in ir2.metadata["verification_checklist"])


# --------------------------------------------------------------------------
# SILENCE
# --------------------------------------------------------------------------


def test_no_checklist_below_the_minimum(handler):
    """One requirement is already fully covered by Key Constraints."""
    ir2 = _ir_v2(_c("❌ RESTRICTION: Exclude soft-deleted rows."))

    handler.handle(ir2, _ir_v1())

    assert "verification_checklist" not in ir2.metadata
    assert render_verification_block(ir2, "en") == []


def test_no_checklist_without_constraints(handler):
    ir2 = _ir_v2()

    handler.handle(ir2, _ir_v1())

    assert "verification_checklist" not in ir2.metadata


@pytest.mark.parametrize("text", ["merhaba", "hi", "make it better", "Write a haiku about rain."])
def test_trivial_and_simple_requests_get_no_checklist(text):
    """Short or unconstrained requests must not be padded with a checklist."""
    assert "Before you finish" not in emit_system_prompt_v2(compile_text_v2(text))


# --------------------------------------------------------------------------
# RENDERING
# --------------------------------------------------------------------------


def test_render_uses_the_ir_language():
    ir2 = _ir_v2(language="tr")
    ir2.metadata["verification_checklist"] = ["Bagimlilik ekleme.", "Silinmis satirlari disla."]

    lines = render_verification_block(ir2, "tr")

    assert lines[0].startswith("Bitirmeden once")
    assert lines[1] == "- [ ] Bagimlilik ekleme."


def test_render_falls_back_to_english_for_unknown_languages():
    ir2 = _ir_v2()
    ir2.metadata["verification_checklist"] = ["A.", "B."]

    assert render_verification_block(ir2, "de")[0] == render_verification_block(ir2, "en")[0]


def test_system_prompt_includes_the_checklist_end_to_end():
    ir = compile_text_v2(
        "Build a CSV export endpoint. It must not expose user emails and should never "
        "log request bodies. Exclude soft-deleted rows. Do not add new dependencies."
    )

    prompt = emit_system_prompt_v2(ir)

    assert "Before you finish, verify each of these against your answer:" in prompt
    assert "expose user emails" in prompt
    # Grounding: every checklist line restates a constraint already on the IR.
    constraint_text = " ".join(c.text for c in ir.constraints)
    for line in ir.metadata["verification_checklist"]:
        assert line.rstrip(".") in constraint_text


def test_checklist_never_exceeds_the_display_cap(handler):
    many = [_c(f"❌ RESTRICTION: Requirement number {i} must hold.") for i in range(20)]
    ir2 = _ir_v2(*many)

    handler.handle(ir2, _ir_v1())

    assert MIN_ITEMS <= len(ir2.metadata["verification_checklist"]) <= 7
