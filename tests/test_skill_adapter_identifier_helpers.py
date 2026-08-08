"""Direct unit coverage for app.adapters.skill_adapter identifier helpers.

`_capitalize_words`, `_to_kebab`, `_to_python_identifier`,
`_to_python_param_identifier`, and `_needs_keyword_only_params` turn
arbitrary skill/param names into safe Python identifiers and SKILL.md
frontmatter names. They are pure string/list transforms with several
edge cases (empty input, leading digits, Python keyword collisions) that
were previously only exercised incidentally through end-to-end export
tests, never asserted directly.
"""

from app.adapters.skill_adapter import (
    _capitalize_words,
    _needs_keyword_only_params,
    _to_kebab,
    _to_python_identifier,
    _to_python_param_identifier,
)
from app.adapters.skill_ir import SkillParam


class TestCapitalizeWords:
    def test_splits_and_capitalizes_each_word(self):
        assert _capitalize_words("hello_world") == ["Hello", "World"]

    def test_single_word(self):
        assert _capitalize_words("single") == ["Single"]

    def test_lowercases_rest_of_already_mixed_case_word(self):
        assert _capitalize_words("hELLO_wORLD") == ["Hello", "World"]

    def test_empty_string_yields_single_empty_element(self):
        assert _capitalize_words("") == [""]


class TestToKebab:
    def test_converts_snake_case_to_kebab_case(self):
        assert _to_kebab("hello_world") == "hello-world"

    def test_collapses_repeated_underscores(self):
        assert _to_kebab("hello__world") == "hello-world"

    def test_strips_leading_and_trailing_underscores(self):
        assert _to_kebab("__hello_world__") == "hello-world"

    def test_lowercases_input(self):
        assert _to_kebab("HELLO_WORLD") == "hello-world"

    def test_empty_string(self):
        assert _to_kebab("") == ""


class TestToPythonIdentifier:
    def test_lowercases_and_underscores_non_alnum(self):
        assert _to_python_identifier("My Skill!") == "my_skill"

    def test_collapses_repeated_separators(self):
        assert _to_python_identifier("my--skill  name") == "my_skill_name"

    def test_leading_digit_gets_prefixed(self):
        assert _to_python_identifier("123abc") == "skill_123abc"

    def test_python_keyword_gets_suffixed(self):
        assert _to_python_identifier("class") == "class_skill"

    def test_empty_input_falls_back_to_skill(self):
        assert _to_python_identifier("") == "skill"

    def test_only_symbols_falls_back_to_skill(self):
        assert _to_python_identifier("!!!") == "skill"

    def test_already_valid_identifier_is_unchanged(self):
        assert _to_python_identifier("get_weather") == "get_weather"


class TestToPythonParamIdentifier:
    def test_replaces_invalid_characters(self):
        assert _to_python_param_identifier("user-name") == "user_name"

    def test_preserves_case_unlike_skill_identifier(self):
        assert _to_python_param_identifier("My Param") == "My_Param"

    def test_leading_digit_gets_param_prefix(self):
        assert _to_python_param_identifier("2fa") == "param_2fa"

    def test_python_keyword_gets_trailing_underscore(self):
        assert _to_python_param_identifier("class") == "class_"

    def test_empty_input_falls_back_to_param(self):
        assert _to_python_param_identifier("") == "param"


class TestNeedsKeywordOnlyParams:
    def _param(self, name: str, required: bool) -> SkillParam:
        return SkillParam(name=name, required=required)

    def test_no_params_does_not_need_keyword_only(self):
        assert _needs_keyword_only_params([]) is False

    def test_all_required_does_not_need_keyword_only(self):
        params = [self._param("a", True), self._param("b", True)]
        assert _needs_keyword_only_params(params) is False

    def test_required_after_optional_needs_keyword_only(self):
        params = [self._param("a", False), self._param("b", True)]
        assert _needs_keyword_only_params(params) is True

    def test_optional_after_required_does_not_need_keyword_only(self):
        params = [self._param("a", True), self._param("b", False)]
        assert _needs_keyword_only_params(params) is False

    def test_required_after_run_of_optionals_needs_keyword_only(self):
        params = [
            self._param("a", False),
            self._param("b", False),
            self._param("c", True),
        ]
        assert _needs_keyword_only_params(params) is True

    def test_all_optional_does_not_need_keyword_only(self):
        params = [self._param("a", False), self._param("b", False)]
        assert _needs_keyword_only_params(params) is False
