from app.adapters.skill_adapter import (
    SkillExample,
    SkillParam,
    _capitalize_words,
    _example_value_for,
    _needs_keyword_only_params,
    _render_bullets_block,
    _render_examples_block,
    _render_inputs_block,
    _to_kebab,
    _to_python_identifier,
    _to_python_param_identifier,
    _to_title,
    _unwrap_to_base,
    _yaml_safe,
)


def test_capitalize_words_splits_on_underscore():
    assert _capitalize_words("send_email_now") == ["Send", "Email", "Now"]


def test_capitalize_words_single_word():
    assert _capitalize_words("skill") == ["Skill"]


def test_to_title_joins_with_spaces():
    assert _to_title("send_email_now") == "Send Email Now"


def test_to_title_empty_string():
    assert _to_title("") == ""


def test_to_kebab_converts_underscores_to_hyphens():
    assert _to_kebab("send_email_now") == "send-email-now"


def test_to_kebab_collapses_repeated_underscores():
    assert _to_kebab("send__email___now") == "send-email-now"


def test_to_kebab_strips_leading_trailing_underscores():
    assert _to_kebab("_send_email_") == "send-email"


def test_to_kebab_lowercases():
    assert _to_kebab("Send_Email") == "send-email"


def test_to_python_identifier_sanitizes_special_characters():
    assert _to_python_identifier("Send Email!!") == "send_email"


def test_to_python_identifier_empty_falls_back_to_skill():
    assert _to_python_identifier("!!!") == "skill"


def test_to_python_identifier_leading_digit_gets_prefixed():
    assert _to_python_identifier("123skill") == "skill_123skill"


def test_to_python_identifier_python_keyword_gets_suffixed():
    assert _to_python_identifier("class") == "class_skill"


def test_to_python_param_identifier_sanitizes_special_characters():
    assert _to_python_param_identifier("user-name!") == "user_name"


def test_to_python_param_identifier_empty_falls_back_to_param():
    assert _to_python_param_identifier("!!!") == "param"


def test_to_python_param_identifier_leading_digit_gets_prefixed():
    assert _to_python_param_identifier("1st") == "param_1st"


def test_to_python_param_identifier_python_keyword_gets_suffixed():
    assert _to_python_param_identifier("import") == "import_"


def test_needs_keyword_only_params_false_when_all_required():
    params = [SkillParam(name="a", required=True), SkillParam(name="b", required=True)]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_false_when_optional_is_last():
    params = [SkillParam(name="a", required=True), SkillParam(name="b", required=False)]
    assert _needs_keyword_only_params(params) is False


def test_needs_keyword_only_params_true_when_required_follows_optional():
    params = [
        SkillParam(name="a", required=False),
        SkillParam(name="b", required=True),
    ]
    assert _needs_keyword_only_params(params) is True


def test_example_value_for_no_examples_returns_none():
    param = SkillParam(name="city")
    assert _example_value_for(param, []) is None


def test_example_value_for_double_quoted_value():
    param = SkillParam(name="city")
    examples = [SkillExample(input='city="Paris", days=3', output="ok")]
    assert _example_value_for(param, examples) == "Paris"


def test_example_value_for_colon_style_value():
    param = SkillParam(name="city")
    examples = [SkillExample(input="city: London", output="ok")]
    assert _example_value_for(param, examples) == "London"


def test_example_value_for_no_match_returns_none():
    param = SkillParam(name="missing")
    examples = [SkillExample(input="city=Paris", output="ok")]
    assert _example_value_for(param, examples) is None


def test_unwrap_to_base_plain_type():
    assert _unwrap_to_base("int") == "int"


def test_unwrap_to_base_optional():
    assert _unwrap_to_base("Optional[str]") == "str"


def test_unwrap_to_base_typing_optional():
    assert _unwrap_to_base("typing.Optional[int]") == "int"


def test_unwrap_to_base_union():
    assert _unwrap_to_base("Union[str, None]") == "str"


def test_unwrap_to_base_pipe_union():
    assert _unwrap_to_base("str | None") == "str"


def test_unwrap_to_base_generic():
    assert _unwrap_to_base("list[str]") == "list"


def test_unwrap_to_base_namespaced():
    assert _unwrap_to_base("typing.Dict") == "dict"


def test_unwrap_to_base_empty_string():
    assert _unwrap_to_base("") == ""


def test_unwrap_to_base_non_string_input():
    assert _unwrap_to_base(None) == ""


def test_yaml_safe_plain_value_unquoted():
    assert _yaml_safe("hello-world") == "hello-world"


def test_yaml_safe_reserved_word_gets_quoted():
    assert _yaml_safe("yes") == '"yes"'
    assert _yaml_safe("true") == '"true"'


def test_yaml_safe_special_characters_get_quoted_and_escaped():
    assert _yaml_safe('has "quotes"') == '"has \\"quotes\\""'


def test_yaml_safe_colon_triggers_quoting():
    assert _yaml_safe("key: value") == '"key: value"'


def test_yaml_safe_strips_newlines():
    assert _yaml_safe("line one\nline two") == "line one line two"


def test_render_inputs_block_no_params():
    from app.adapters.skill_ir import SkillExportIR

    ir = SkillExportIR(name="skill", params=[])
    assert _render_inputs_block(ir) == "_No inputs._"


def test_render_inputs_block_with_param_and_example():
    from app.adapters.skill_ir import SkillExportIR

    ir = SkillExportIR(
        name="skill",
        params=[SkillParam(name="city", type="str", description="City name", required=True)],
        examples=[SkillExample(input='city="Paris"', output="ok")],
    )
    result = _render_inputs_block(ir)
    assert "`city`" in result
    assert "required" in result
    assert "City name" in result
    assert "Paris" in result


def test_render_examples_block_empty_returns_empty_string():
    assert _render_examples_block([]) == ""


def test_render_examples_block_with_examples():
    examples = [SkillExample(input="city=Paris", output="sunny")]
    result = _render_examples_block(examples)
    assert "## Examples" in result
    assert "city=Paris" in result
    assert "sunny" in result


def test_render_bullets_block_empty_returns_empty_string():
    assert _render_bullets_block("Dependencies", []) == ""


def test_render_bullets_block_with_items():
    result = _render_bullets_block("Dependencies", ["requests", "pydantic"])
    assert "## Dependencies" in result
    assert "- requests" in result
    assert "- pydantic" in result
