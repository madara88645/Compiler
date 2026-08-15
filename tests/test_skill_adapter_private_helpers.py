"""
Coverage for small, pure, string-shaping helpers in app/adapters/skill_adapter.py
that are used by the LangChain / Claude tool_use / Agent Skill exporters but were
not directly exercised by any existing test.
"""

from __future__ import annotations

from app.adapters.skill_adapter import (
    _capitalize_words,
    _needs_keyword_only_params,
    _to_kebab,
    _to_title,
    _truncate_at_sentence,
    _unwrap_to_base,
    _yaml_safe,
)
from app.adapters.skill_ir import SkillParam


# ---------------------------------------------------------------------------
# _needs_keyword_only_params
# ---------------------------------------------------------------------------


class TestNeedsKeywordOnlyParams:
    def test_empty_list_is_false(self):
        assert _needs_keyword_only_params([]) is False

    def test_all_required_is_false(self):
        params = [
            SkillParam(name="a", required=True),
            SkillParam(name="b", required=True),
        ]
        assert _needs_keyword_only_params(params) is False

    def test_all_optional_is_false(self):
        params = [
            SkillParam(name="a", required=False),
            SkillParam(name="b", required=False),
        ]
        assert _needs_keyword_only_params(params) is False

    def test_required_then_optional_is_false(self):
        """Trailing optionals after required params don't need `*`."""
        params = [
            SkillParam(name="a", required=True),
            SkillParam(name="b", required=False),
        ]
        assert _needs_keyword_only_params(params) is False

    def test_optional_then_required_is_true(self):
        """A required param following an optional one forces keyword-only."""
        params = [
            SkillParam(name="a", required=False),
            SkillParam(name="b", required=True),
        ]
        assert _needs_keyword_only_params(params) is True

    def test_required_optional_required_is_true(self):
        params = [
            SkillParam(name="a", required=True),
            SkillParam(name="b", required=False),
            SkillParam(name="c", required=True),
        ]
        assert _needs_keyword_only_params(params) is True

    def test_single_required_param_is_false(self):
        assert _needs_keyword_only_params([SkillParam(name="a", required=True)]) is False

    def test_single_optional_param_is_false(self):
        assert _needs_keyword_only_params([SkillParam(name="a", required=False)]) is False


# ---------------------------------------------------------------------------
# _yaml_safe
# ---------------------------------------------------------------------------


class TestYamlSafe:
    def test_plain_word_is_returned_bare(self):
        assert _yaml_safe("hello world") == "hello world"

    def test_reserved_word_yes_is_quoted(self):
        assert _yaml_safe("yes") == '"yes"'

    def test_reserved_word_is_case_insensitive_but_preserves_original_case(self):
        assert _yaml_safe("YES") == '"YES"'
        assert _yaml_safe("True") == '"True"'
        assert _yaml_safe("Null") == '"Null"'
        assert _yaml_safe("~") == '"~"'

    def test_colon_triggers_quoting(self):
        assert _yaml_safe("a: b") == '"a: b"'

    def test_hash_triggers_quoting(self):
        assert _yaml_safe("value #note") == '"value #note"'

    def test_embedded_double_quote_is_escaped(self):
        assert _yaml_safe('He said "hi"') == '"He said \\"hi\\""'

    def test_backslash_is_escaped_when_quoting_is_triggered(self):
        # A backslash alone isn't a "special char" trigger, but once quoting is
        # triggered by another special char, existing backslashes must be escaped
        # so the output round-trips as valid YAML.
        assert _yaml_safe('C:\\path') == '"C:\\\\path"'

    def test_newline_and_carriage_return_collapsed_to_space(self):
        assert _yaml_safe("line1\nline2") == "line1 line2"
        assert _yaml_safe("line1\r\nline2") == "line1  line2"

    def test_surrounding_whitespace_is_stripped(self):
        assert _yaml_safe("  hello  ") == "hello"

    def test_each_special_char_triggers_quoting(self):
        for ch in (":", "#", "`", '"', "'", "[", "]", "{", "}", "&", "*", "!", "|", ">", "%", "@"):
            value = f"a{ch}b"
            result = _yaml_safe(value)
            assert result.startswith('"') and result.endswith('"'), (ch, result)


# ---------------------------------------------------------------------------
# _truncate_at_sentence
# ---------------------------------------------------------------------------


class TestTruncateAtSentence:
    def test_text_shorter_than_max_len_is_unchanged(self):
        text = "Short text."
        assert _truncate_at_sentence(text, 200) == text

    def test_text_exactly_max_len_is_unchanged(self):
        text = "x" * 50
        assert _truncate_at_sentence(text, 50) == text

    def test_truncates_at_sentence_boundary_when_found_past_halfway(self):
        # Sentence boundary ". " falls after max_len // 2, so it wins over the
        # generic word-boundary fallback.
        text = "A" * 30 + ". " + "B" * 100
        result = _truncate_at_sentence(text, 60)
        assert result == "A" * 30 + "."
        assert not result.endswith("…")

    def test_prefers_exclamation_terminator_past_halfway(self):
        # "! " sits at index 32, past max_len // 2 == 30, so it wins.
        text = ("a" * 32) + "! " + ("z" * 100)
        result = _truncate_at_sentence(text, 60)
        assert result == ("a" * 32) + "!"

    def test_prefers_question_terminator_past_halfway(self):
        text = ("a" * 32) + "? " + ("z" * 100)
        result = _truncate_at_sentence(text, 60)
        assert result == ("a" * 32) + "?"

    def test_no_sentence_boundary_falls_back_to_word_boundary_with_ellipsis(self):
        # No ". "/"! "/"? " within the cut at all -> falls back to last space.
        text = "word " * 40  # no sentence terminators anywhere
        result = _truncate_at_sentence(text, 60)
        assert result.endswith("…")
        assert ". " not in result

    def test_word_boundary_fallback_strips_trailing_punctuation(self):
        # The only space in range is right after "alpha,"; the trailing comma
        # must be stripped before the ellipsis is appended.
        text = "alpha, " + "b" * 100
        result = _truncate_at_sentence(text, 13)
        assert result == "alpha…"

    def test_no_boundary_found_early_enough_hard_cuts_with_ellipsis(self):
        # A single very long unbroken token with no space/sentence terminator
        # before the halfway point forces a hard cut.
        text = "x" * 200
        result = _truncate_at_sentence(text, 50)
        assert result == "x" * 50 + "…"

    def test_sentence_boundary_before_halfway_is_ignored(self):
        # ". " occurs at index 2 (well before max_len // 2 == 30), so it must
        # not be used as the cut point; the word-boundary rule takes over and
        # the result is far longer than just "Hi.".
        text = "Hi. " + ("word " * 40)
        result = _truncate_at_sentence(text, 60)
        assert result != "Hi."
        assert result.endswith("…")
        assert len(result) > len("Hi.")


# ---------------------------------------------------------------------------
# _to_kebab / _to_title / _capitalize_words
# ---------------------------------------------------------------------------


class TestCapitalizeWords:
    def test_splits_and_capitalizes_each_underscore_word(self):
        assert _capitalize_words("hello_world") == ["Hello", "World"]

    def test_lowercases_rest_of_already_uppercase_word(self):
        assert _capitalize_words("HELLO_WORLD") == ["Hello", "World"]

    def test_single_word_no_underscore(self):
        assert _capitalize_words("single") == ["Single"]

    def test_empty_string_yields_single_empty_element(self):
        assert _capitalize_words("") == [""]


class TestToKebab:
    def test_simple_snake_case(self):
        assert _to_kebab("my_skill_name") == "my-skill-name"

    def test_collapses_multiple_underscores_to_one_hyphen(self):
        assert _to_kebab("my__skill___name") == "my-skill-name"

    def test_strips_leading_and_trailing_underscores(self):
        assert _to_kebab("_my_skill_") == "my-skill"

    def test_uppercase_is_lowercased(self):
        assert _to_kebab("My_Skill_Name") == "my-skill-name"

    def test_single_word_no_underscore(self):
        assert _to_kebab("skill") == "skill"

    def test_all_underscores_yields_empty_string(self):
        assert _to_kebab("___") == ""


class TestToTitle:
    def test_simple_snake_case(self):
        assert _to_title("hello_world") == "Hello World"

    def test_single_word(self):
        assert _to_title("skill") == "Skill"

    def test_all_uppercase_input_normalized(self):
        assert _to_title("WEATHER_LOOKUP") == "Weather Lookup"

    def test_empty_string(self):
        assert _to_title("") == ""


# ---------------------------------------------------------------------------
# _unwrap_to_base
# ---------------------------------------------------------------------------


class TestUnwrapToBase:
    def test_non_string_input_returns_empty_string(self):
        assert _unwrap_to_base(None) == ""
        assert _unwrap_to_base(123) == ""

    def test_empty_string_returns_empty_string(self):
        assert _unwrap_to_base("") == ""
        assert _unwrap_to_base("   ") == ""

    def test_plain_base_type_lowercased(self):
        assert _unwrap_to_base("Str") == "str"
        assert _unwrap_to_base("INT") == "int"

    def test_strips_optional_wrapper(self):
        assert _unwrap_to_base("Optional[int]") == "int"
        assert _unwrap_to_base("typing.Optional[str]") == "str"

    def test_strips_union_wrapper_taking_first_non_none(self):
        assert _unwrap_to_base("Union[str, None]") == "str"
        assert _unwrap_to_base("typing.Union[int, str, None]") == "int"

    def test_union_of_only_none_falls_back_to_any(self):
        assert _unwrap_to_base("Union[None, NoneType]") == "any"

    def test_strips_pipe_union_taking_first_non_none(self):
        assert _unwrap_to_base("int | None") == "int"
        assert _unwrap_to_base("None | float") == "float"

    def test_extracts_generic_base(self):
        assert _unwrap_to_base("List[str]") == "list"
        assert _unwrap_to_base("Dict[str, int]") == "dict"

    def test_strips_module_namespace(self):
        assert _unwrap_to_base("typing.List[str]") == "list"
        assert _unwrap_to_base("collections.abc.Mapping[str, str]") == "mapping"

    def test_nested_generic_with_optional_and_namespace(self):
        assert _unwrap_to_base("Optional[typing.List[str]]") == "list"

    def test_whitespace_normalized_around_brackets(self):
        assert _unwrap_to_base("List [ str ]") == "list"


# ---------------------------------------------------------------------------
# Legacy-bug guard: reserved-word check is genuinely case-insensitive
# ---------------------------------------------------------------------------


def test_yaml_safe_reserved_word_off_variant():
    assert _yaml_safe("Off") == '"Off"'
    assert _yaml_safe("no") == '"no"'
