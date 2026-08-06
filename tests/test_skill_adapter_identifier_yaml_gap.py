"""Unit tests for skill_adapter's identifier/YAML/truncation helpers.

_to_python_identifier, _to_python_param_identifier, _yaml_safe, and
_truncate_at_sentence are pure string helpers reached only transitively
through the adapter's public to_langchain_tool/to_agent_skill tests. None of
them had a direct test before this file, despite handling edge cases
(keyword collisions, YAML-reserved words, sentence-boundary truncation) that
are easy to regress silently.
"""

from __future__ import annotations

from app.adapters.skill_adapter import (
    _to_python_identifier,
    _to_python_param_identifier,
    _truncate_at_sentence,
    _yaml_safe,
)


def test_to_python_identifier_normalizes_symbols_and_case():
    assert _to_python_identifier("My Skill-Name!") == "my_skill_name"


def test_to_python_identifier_empty_input_falls_back():
    assert _to_python_identifier("") == "skill"
    assert _to_python_identifier("***") == "skill"


def test_to_python_identifier_leading_digit_gets_prefixed():
    assert _to_python_identifier("123start") == "skill_123start"


def test_to_python_identifier_keyword_collision_gets_suffixed():
    assert _to_python_identifier("class") == "class_skill"
    assert _to_python_identifier("for") == "for_skill"


def test_to_python_identifier_collapses_repeated_underscores():
    assert _to_python_identifier("a___b") == "a_b"


def test_to_python_param_identifier_normalizes_symbols():
    assert _to_python_param_identifier("My Param!") == "My_Param"


def test_to_python_param_identifier_empty_input_falls_back():
    assert _to_python_param_identifier("") == "param"
    assert _to_python_param_identifier("***") == "param"


def test_to_python_param_identifier_leading_digit_gets_prefixed():
    assert _to_python_param_identifier("123count") == "param_123count"


def test_to_python_param_identifier_keyword_collision_gets_suffixed():
    assert _to_python_param_identifier("class") == "class_"


def test_yaml_safe_plain_string_is_unquoted():
    assert _yaml_safe("a plain description") == "a plain description"


def test_yaml_safe_reserved_word_is_quoted():
    assert _yaml_safe("true") == '"true"'
    assert _yaml_safe("Null") == '"Null"'


def test_yaml_safe_special_char_is_quoted_and_escaped():
    assert _yaml_safe('has: a colon') == '"has: a colon"'
    assert _yaml_safe('has "quotes"') == '"has \\"quotes\\""'


def test_yaml_safe_strips_newlines_and_carriage_returns():
    assert _yaml_safe("line one\nline two\r") == "line one line two"


def test_truncate_at_sentence_returns_unchanged_when_under_limit():
    assert _truncate_at_sentence("short text", 50) == "short text"


def test_truncate_at_sentence_cuts_at_sentence_boundary():
    text = "First sentence. Second sentence. Third sentence that is long."
    result = _truncate_at_sentence(text, 35)
    assert result == "First sentence. Second sentence."


def test_truncate_at_sentence_falls_back_to_word_boundary():
    text = "wordwordword wordwordword wordwordword wordwordword nopunctuation"
    result = _truncate_at_sentence(text, 30)
    assert result.endswith("…")
    assert "." not in result
    assert len(result) <= 31


def test_truncate_at_sentence_hard_cuts_when_no_spaces():
    text = "a" * 50
    result = _truncate_at_sentence(text, 10)
    assert result == "a" * 10 + "…"
