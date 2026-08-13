"""Direct unit tests for pure helper functions in skill_adapter.py and
agent_ir.py that had zero prior coverage: identifier sanitization,
keyword-only-param detection, example-value extraction, casing helpers,
and section-alias collision resolution.
"""
from app.adapters.skill_adapter import (
    _capitalize_words,
    _example_value_for,
    _needs_keyword_only_params,
    _resolve_example_map,
    _to_kebab,
    _to_python_identifier,
    _to_python_param_identifier,
    _to_title,
)
from app.adapters.skill_ir import SkillExample, SkillParam
from app.adapters.agent_ir import _map_sections, _SECTION_ALIASES


# --- _to_python_identifier ------------------------------------------------


def test_to_python_identifier_normal():
    assert _to_python_identifier("my_skill") == "my_skill"


def test_to_python_identifier_leading_digit():
    identifier = _to_python_identifier("123skill")
    assert identifier == "skill_123skill"
    assert not identifier[0].isdigit()


def test_to_python_identifier_keyword():
    assert _to_python_identifier("class") == "class_skill"
    assert _to_python_identifier("def") == "def_skill"


def test_to_python_identifier_invalid_chars():
    assert _to_python_identifier("my skill-name.v2") == "my_skill_name_v2"


def test_to_python_identifier_empty():
    assert _to_python_identifier("") == "skill"


# --- _to_python_param_identifier ------------------------------------------


def test_to_python_param_identifier_normal():
    assert _to_python_param_identifier("my_param") == "my_param"


def test_to_python_param_identifier_leading_digit():
    identifier = _to_python_param_identifier("123param")
    assert identifier == "param_123param"
    assert not identifier[0].isdigit()


def test_to_python_param_identifier_keyword():
    assert _to_python_param_identifier("class") == "class_"
    assert _to_python_param_identifier("def") == "def_"


def test_to_python_param_identifier_invalid_chars():
    assert _to_python_param_identifier("my param-name.v2") == "my_param_name_v2"


def test_to_python_param_identifier_empty():
    assert _to_python_param_identifier("") == "param"


def test_identifier_vs_param_identifier_prefix_suffix_differ():
    # Same keyword input: function-name convention appends "_skill" and
    # lowercases; param convention just appends a trailing underscore.
    assert _to_python_identifier("class") == "class_skill"
    assert _to_python_param_identifier("class") == "class_"

    # Same leading-digit input: function-name convention prefixes "skill_",
    # param convention prefixes "param_".
    assert _to_python_identifier("1x") == "skill_1x"
    assert _to_python_param_identifier("1x") == "param_1x"

    # Function-identifier convention lowercases; param convention does not.
    assert _to_python_identifier("MyName") == "myname"
    assert _to_python_param_identifier("MyName") == "MyName"


# --- _needs_keyword_only_params -------------------------------------------


def test_needs_keyword_only_params_required_after_optional():
    params = [
        SkillParam(name="a", required=False),
        SkillParam(name="b", required=True),
    ]
    assert _needs_keyword_only_params(params) is True


def test_needs_keyword_only_params_all_required():
    params = [
        SkillParam(name="a", required=True),
        SkillParam(name="b", required=True),
    ]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_all_optional():
    params = [
        SkillParam(name="a", required=False),
        SkillParam(name="b", required=False),
    ]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_empty():
    assert _needs_keyword_only_params([]) is False


def test_needs_keyword_only_params_optional_last_is_fine():
    params = [
        SkillParam(name="a", required=True),
        SkillParam(name="b", required=False),
    ]
    assert _needs_keyword_only_params(params) is False


# --- _example_value_for ----------------------------------------------------


def test_example_value_for_double_quoted():
    param = SkillParam(name="city")
    examples = [SkillExample(input='city: "Paris"', output="ok")]
    assert _example_value_for(param, examples) == "Paris"


def test_example_value_for_single_quoted():
    param = SkillParam(name="city")
    examples = [SkillExample(input="city='London'", output="ok")]
    assert _example_value_for(param, examples) == "London"


def test_example_value_for_unquoted():
    param = SkillParam(name="count")
    examples = [SkillExample(input="count=42", output="ok")]
    assert _example_value_for(param, examples) == "42"


def test_example_value_for_no_match():
    param = SkillParam(name="missing")
    examples = [SkillExample(input='city: "Paris"', output="ok")]
    assert _example_value_for(param, examples) is None


def test_example_value_for_no_examples():
    param = SkillParam(name="city")
    assert _example_value_for(param, []) is None


# --- _resolve_example_map ---------------------------------------------------


def test_resolve_example_map_multiple_params():
    params = [
        SkillParam(name="city"),
        SkillParam(name="count"),
        SkillParam(name="missing"),
    ]
    examples = [SkillExample(input='city: "Paris", count=3', output="ok")]
    result = _resolve_example_map(params, examples)
    assert result == {"city": "Paris", "count": "3", "missing": None}


# --- _capitalize_words / _to_kebab / _to_title ------------------------------


def test_capitalize_words():
    assert _capitalize_words("hello_world") == ["Hello", "World"]
    assert _capitalize_words("single") == ["Single"]


def test_to_kebab():
    assert _to_kebab("my_skill_name") == "my-skill-name"
    assert _to_kebab("__leading_trailing__") == "leading-trailing"


def test_to_title():
    assert _to_title("my_skill_name") == "My Skill Name"
    assert _to_title("single") == "Single"


# --- _map_sections (agent_ir.py) --------------------------------------------


def test_map_sections_no_collision():
    sections = {
        "role": "You are an assistant.",
        "goals": "Help users.",
        "constraints": "Be concise.",
    }
    mapped = _map_sections(sections)
    assert mapped == {
        "role": "You are an assistant.",
        "goals": "Help users.",
        "constraints": "Be concise.",
    }


def test_map_sections_unknown_key_dropped():
    sections = {"role": "You are an assistant.", "totally_unknown": "ignored"}
    mapped = _map_sections(sections)
    assert mapped == {"role": "You are an assistant."}
    assert "totally_unknown" not in mapped


def test_map_sections_collision_first_alias_wins():
    # "goals" and "objective" both alias to canonical "goals" in
    # _SECTION_ALIASES. Confirm that assumption directly from the table,
    # then verify insertion order determines which content wins.
    assert _SECTION_ALIASES["goals"] == "goals"
    assert _SECTION_ALIASES["objective"] == "goals"

    sections = {
        "goals": "first goals content",
        "objective": "second goals content",
    }
    mapped = _map_sections(sections)
    assert mapped["goals"] == "first goals content"

    # Reversing insertion order flips which content wins, proving it is
    # genuinely "first key encountered" and not alphabetical or fixed.
    sections_reversed = {
        "objective": "second goals content",
        "goals": "first goals content",
    }
    mapped_reversed = _map_sections(sections_reversed)
    assert mapped_reversed["goals"] == "second goals content"


def test_map_sections_constraints_alias_collision():
    # "rules" and "limitations" both alias to canonical "constraints".
    assert _SECTION_ALIASES["rules"] == "constraints"
    assert _SECTION_ALIASES["limitations"] == "constraints"

    sections = {
        "rules": "rules content",
        "limitations": "limitations content",
    }
    mapped = _map_sections(sections)
    assert mapped["constraints"] == "rules content"
