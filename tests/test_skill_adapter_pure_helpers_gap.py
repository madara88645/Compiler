"""Direct unit tests for pure helpers in app.adapters.skill_adapter that were
not covered by tests/test_skill_adapter.py: `_needs_keyword_only_params`,
`_truncate_at_sentence`, `_to_kebab`, `_to_title`, and `_capitalize_words`.

`_to_pascal` (sibling case-conversion helper) is already covered in
tests/test_skill_adapter.py::test_to_pascal.
"""

from app.adapters.skill_adapter import (
    _capitalize_words,
    _needs_keyword_only_params,
    _to_kebab,
    _to_title,
    _truncate_at_sentence,
)
from app.adapters.skill_ir import SkillParam


# --- _capitalize_words / _to_kebab / _to_title ------------------------------


def test_capitalize_words_splits_and_capitalizes_each_segment():
    assert _capitalize_words("hello_world") == ["Hello", "World"]


def test_capitalize_words_single_segment():
    assert _capitalize_words("single") == ["Single"]


def test_capitalize_words_empty_string_returns_single_empty_segment():
    assert _capitalize_words("") == [""]


def test_to_kebab_converts_underscores_to_hyphens():
    assert _to_kebab("my_skill_name") == "my-skill-name"


def test_to_kebab_collapses_repeated_underscores():
    assert _to_kebab("a__b___c") == "a-b-c"


def test_to_kebab_strips_leading_and_trailing_underscores():
    assert _to_kebab("__hello_world__") == "hello-world"


def test_to_kebab_lowercases_input():
    assert _to_kebab("My_Skill") == "my-skill"


def test_to_title_joins_capitalized_words_with_spaces():
    assert _to_title("hello_world") == "Hello World"


def test_to_title_single_word():
    assert _to_title("single") == "Single"


# --- _needs_keyword_only_params ---------------------------------------------


def _param(name: str, required: bool) -> SkillParam:
    return SkillParam(name=name, type="str", description="", required=required)


def test_needs_keyword_only_params_all_required_is_false():
    params = [_param("a", True), _param("b", True)]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_all_optional_is_false():
    params = [_param("a", False), _param("b", False)]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_required_after_optional_is_true():
    params = [_param("a", False), _param("b", True)]
    assert _needs_keyword_only_params(params) is True


def test_needs_keyword_only_params_optional_after_required_is_false():
    params = [_param("a", True), _param("b", False)]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_empty_list_is_false():
    assert _needs_keyword_only_params([]) is False


def test_needs_keyword_only_params_required_optional_required_is_true():
    params = [_param("a", True), _param("b", False), _param("c", True)]
    assert _needs_keyword_only_params(params) is True


# --- _truncate_at_sentence ----------------------------------------------------


def test_truncate_at_sentence_returns_unchanged_when_within_limit():
    assert _truncate_at_sentence("short text", 100) == "short text"


def test_truncate_at_sentence_returns_unchanged_when_exactly_at_limit():
    text = "12345"
    assert _truncate_at_sentence(text, 5) == text


def test_truncate_at_sentence_breaks_on_sentence_boundary():
    text = "This is the first sentence. This is the second sentence that runs long."
    result = _truncate_at_sentence(text, 40)
    assert result == "This is the first sentence."
    assert not result.endswith("…")


def test_truncate_at_sentence_falls_back_to_word_boundary_when_no_sentence_break():
    # No ". "/"! "/"? " within the cut, but there is a word boundary past
    # max_len // 2, so it should cut at the last space and add an ellipsis.
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    result = _truncate_at_sentence(text, 30)
    assert result.endswith("…")
    assert not result.endswith(" …")


def test_truncate_at_sentence_strips_trailing_punctuation_before_ellipsis():
    text = "word one, word two, word three, word four is long"
    result = _truncate_at_sentence(text, 20)
    # The word boundary falls right after "word two,"; the trailing comma
    # should be stripped before the ellipsis is appended.
    assert result == "word one, word two…"
    assert not result.endswith(",…")


def test_truncate_at_sentence_hard_cutoff_when_no_boundary_found():
    # A single long token with no spaces or sentence punctuation at all.
    text = "a" * 50
    result = _truncate_at_sentence(text, 10)
    assert result == "a" * 10 + "…"


def test_truncate_at_sentence_ignores_sentence_break_before_half_max_len():
    # The only sentence break ("Hi. ") occurs at index 2, well before
    # max_len // 2 == 15, so it must be ignored in favor of the
    # word-boundary fallback rather than truncating down to just "Hi.".
    text = "Hi. " + "word " * 20
    result = _truncate_at_sentence(text, 30)
    assert result == "Hi. word word word word word…"
