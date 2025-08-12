from app.compiler import compile_text


def test_defaults_when_minimal():
    ir = compile_text("Hello")
    assert ir.goals and ir.tasks
    assert ir.output_format in {"markdown","json","yaml","table","text"}
    assert ir.length_hint in {"short","medium","long"}
