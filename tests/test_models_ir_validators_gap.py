"""Coverage gap: app.models.IR field validators (_norm_list, _lang, _fmt,
_persona, _len). Existing tests only ever construct valid IR instances; these
tests assert on the ValueError branches and on _norm_list's dedup/stripping
behavior.
"""
import pytest

from app.models import IR


def _base_kwargs(**overrides):
    kwargs = dict(
        language="en",
        persona="assistant",
        role="test",
        domain="general",
        output_format="markdown",
        length_hint="short",
    )
    kwargs.update(overrides)
    return kwargs


def test_ir_invalid_language_raises_value_error():
    with pytest.raises(ValueError, match="language must be one of"):
        IR(**_base_kwargs(language="fr"))


def test_ir_invalid_output_format_raises_value_error():
    with pytest.raises(ValueError, match="invalid output_format"):
        IR(**_base_kwargs(output_format="pdf"))


def test_ir_invalid_persona_raises_value_error():
    with pytest.raises(ValueError, match="persona must be one of"):
        IR(**_base_kwargs(persona="wizard"))


def test_ir_invalid_length_hint_raises_value_error():
    with pytest.raises(ValueError, match="invalid length_hint"):
        IR(**_base_kwargs(length_hint="epic"))


def test_ir_valid_construction_does_not_raise():
    ir = IR(**_base_kwargs())
    assert ir.language == "en"
    assert ir.persona == "assistant"
    assert ir.output_format == "markdown"
    assert ir.length_hint == "short"


def test_norm_list_dedups_case_insensitively_preserving_first_occurrence():
    ir = IR(**_base_kwargs(goals=["Learn Python", "learn python", "Learn Python", "Ship code"]))
    assert ir.goals == ["Learn Python", "Ship code"]


def test_norm_list_strips_whitespace_and_drops_empties():
    ir = IR(**_base_kwargs(tasks=["  write tests  ", "", "   ", "review PR"]))
    assert ir.tasks == ["write tests", "review PR"]


def test_norm_list_accepts_single_string_and_wraps_in_list():
    ir = IR(**_base_kwargs(constraints="be concise"))
    assert ir.constraints == ["be concise"]


def test_norm_list_none_becomes_empty_list():
    ir = IR(**_base_kwargs(style=None))
    assert ir.style == []


def test_norm_list_default_empty():
    ir = IR(**_base_kwargs())
    assert ir.goals == []
    assert ir.tasks == []
    assert ir.constraints == []
    assert ir.style == []
    assert ir.tone == []
    assert ir.steps == []
    assert ir.examples == []
    assert ir.banned == []
    assert ir.tools == []
