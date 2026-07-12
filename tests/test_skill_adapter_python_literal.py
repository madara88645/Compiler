from app.adapters.skill_adapter import _python_literal_for


def test_python_literal_for_int():
    assert _python_literal_for("42", "int") == "42"


def test_python_literal_for_float():
    assert _python_literal_for("3.14", "float") == "3.14"


def test_python_literal_for_bool_true_variants():
    assert _python_literal_for("true", "bool") == "True"
    assert _python_literal_for("yes", "bool") == "True"
    assert _python_literal_for("1", "bool") == "True"


def test_python_literal_for_bool_false():
    assert _python_literal_for("false", "bool") == "False"


def test_python_literal_for_string_is_json_quoted():
    assert _python_literal_for("hello", "str") == '"hello"'


def test_python_literal_for_string_with_special_characters_is_escaped():
    result = _python_literal_for('has "quotes" and\nnewline', "str")
    assert result == '"has \\"quotes\\" and\\nnewline"'


def test_python_literal_for_non_numeric_int_falls_back_to_string():
    result = _python_literal_for("not-a-number", "int")
    assert result == '"not-a-number"'
