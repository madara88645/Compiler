"""Direct unit tests for two pure helpers in app.adapters.skill_adapter:

* `_needs_keyword_only_params` — decides whether generated Python needs a
  `*` keyword-only separator when a required param follows an optional one.
* `_example_value_for` — regex-based extraction of an example value for a
  given param from a skill's recorded examples.
"""

from __future__ import annotations

from app.adapters.skill_adapter import _example_value_for, _needs_keyword_only_params
from app.adapters.skill_ir import SkillExample, SkillParam


def _param(name: str, required: bool = True, type: str = "str") -> SkillParam:
    return SkillParam(name=name, type=type, required=required)


class TestNeedsKeywordOnlyParams:
    def test_empty_list_returns_false(self):
        assert _needs_keyword_only_params([]) is False

    def test_all_required_returns_false(self):
        params = [_param("a"), _param("b")]
        assert _needs_keyword_only_params(params) is False

    def test_all_optional_returns_false(self):
        params = [_param("a", required=False), _param("b", required=False)]
        assert _needs_keyword_only_params(params) is False

    def test_required_after_optional_returns_true(self):
        params = [_param("a", required=False), _param("b", required=True)]
        assert _needs_keyword_only_params(params) is True

    def test_optional_after_required_returns_false(self):
        # Normal Python-valid order: no keyword-only separator needed.
        params = [_param("a", required=True), _param("b", required=False)]
        assert _needs_keyword_only_params(params) is False

    def test_required_optional_required_returns_true(self):
        params = [
            _param("a", required=True),
            _param("b", required=False),
            _param("c", required=True),
        ]
        assert _needs_keyword_only_params(params) is True

    def test_single_optional_param_returns_false(self):
        assert _needs_keyword_only_params([_param("a", required=False)]) is False


class TestExampleValueFor:
    def test_no_examples_returns_none(self):
        assert _example_value_for(_param("bar"), []) is None

    def test_double_quoted_value_extracted(self):
        examples = [SkillExample(input='foo(bar="baz")', output="ok")]
        assert _example_value_for(_param("bar"), examples) == "baz"

    def test_single_quoted_value_extracted(self):
        examples = [SkillExample(input="foo(bar='baz')", output="ok")]
        assert _example_value_for(_param("bar"), examples) == "baz"

    def test_bare_numeric_value_extracted(self):
        # The bare-value pattern excludes `,`, whitespace, and `}` but not a
        # closing `)`, so a trailing paren right after the value is captured
        # too — this documents the actual (not idealized) regex behavior.
        examples = [SkillExample(input="foo(count=42)", output="ok")]
        assert _example_value_for(_param("count"), examples) == "42)"

    def test_bare_value_stops_before_comma(self):
        examples = [SkillExample(input="foo(count=42, other=1)", output="ok")]
        assert _example_value_for(_param("count"), examples) == "42"

    def test_colon_separator_also_matches(self):
        examples = [SkillExample(input='foo(bar: "baz")', output="ok")]
        assert _example_value_for(_param("bar"), examples) == "baz"

    def test_param_not_present_returns_none(self):
        examples = [SkillExample(input="foo(other=1)", output="ok")]
        assert _example_value_for(_param("bar"), examples) is None

    def test_first_matching_example_wins(self):
        examples = [
            SkillExample(input="foo(other=1)", output="ok"),
            SkillExample(input='foo(bar="second")', output="ok"),
        ]
        assert _example_value_for(_param("bar"), examples) == "second"

    def test_regex_special_characters_in_param_name_are_escaped(self):
        examples = [SkillExample(input='get(user.id="123")', output="ok")]
        assert _example_value_for(_param("user.id"), examples) == "123"
