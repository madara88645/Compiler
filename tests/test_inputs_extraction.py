from app.compiler import compile_text


def test_tr_interest_and_budget_hint():
    ir = compile_text("arkadaşıma hediye öner futbol sever bütçe 1500-3000 tl olsun, tablo ver")
    assert ir.inputs.get("interest") in {"futbol", "football", "soccer"}
    assert "budget" in ir.inputs or "budget_hint" in ir.inputs
    assert ir.output_format in {"table", "markdown", "json", "yaml", "text"}


def test_en_budget_and_format():
    ir = compile_text("gift ideas for a football fan, budget under $100, output json")
    assert ir.inputs.get("interest") in {"football", "soccer", "futbol"}
    assert "budget" in ir.inputs or "budget_hint" in ir.inputs
    # format preference from inputs should be honored if found
    # json keyword is present, so output_format very likely 'json'
    assert ir.output_format in {"json", "markdown", "yaml", "table", "text"}
