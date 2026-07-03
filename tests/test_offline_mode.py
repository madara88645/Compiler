import time
from app.compiler import compile_text_v2


def test_offline_mode_enforcer_skips_external_calls():
    # In offline mode, the compilation should be extremely fast (<< 100ms)
    # and it should not trigger ContextStrategist or API-based schema generation.

    start_time = time.time()
    ir2 = compile_text_v2(
        "I need you to write a Python script that scrapes a website. I'm getting a 403 Forbidden error.",
        offline_only=True,
    )
    elapsed = time.time() - start_time

    # Assert fast execution
    assert elapsed < 1.0  # Locally this should be practically instant

    # Context snippets should be empty or not present
    assert "context_snippets" not in ir2.metadata


def test_offline_mode_skips_schema_generation():
    ir2 = compile_text_v2(
        "Extract product_name, price, and stock_count.",
        offline_only=True,
    )

    assert not any(c.id == "schema_enforcement" for c in ir2.constraints)
    assert not any(d.category == "structure" for d in ir2.diagnostics)
