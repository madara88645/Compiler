from app.resources import get_ir_schema_text, get_ir_schema_json, iter_builtin_template_texts


def test_get_ir_schema_text():
    # Test getting schema texts
    schema_v1_text = get_ir_schema_text(v2=False)
    assert isinstance(schema_v1_text, str)
    assert len(schema_v1_text) > 0
    assert "properties" in schema_v1_text

    schema_v2_text = get_ir_schema_text(v2=True)
    assert isinstance(schema_v2_text, str)
    assert len(schema_v2_text) > 0
    assert "properties" in schema_v2_text


def test_get_ir_schema_json():
    # Test parsed JSON schema
    schema_v1_json = get_ir_schema_json(v2=False)
    assert isinstance(schema_v1_json, dict)
    assert "properties" in schema_v1_json

    schema_v2_json = get_ir_schema_json(v2=True)
    assert isinstance(schema_v2_json, dict)
    assert "properties" in schema_v2_json


def test_iter_builtin_template_texts():
    # Test retrieving builtin templates
    templates = iter_builtin_template_texts()
    assert isinstance(templates, list)
    # Check if we have templates in the list
    if len(templates) > 0:
        for name, content in templates:
            assert isinstance(name, str)
            assert isinstance(content, str)
            assert name.endswith((".yaml", ".yml"))
