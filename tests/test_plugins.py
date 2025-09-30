from __future__ import annotations

import pytest

from app import plugins
from app.compiler import compile_text
from app.plugins import describe_plugins


@pytest.fixture(autouse=True)
def _reset_plugins(monkeypatch):
    monkeypatch.setenv("PROMPTC_PLUGIN_PATH", "tests.sample_plugin")
    plugins.reset_plugin_cache()
    yield
    plugins.reset_plugin_cache()


def test_plugin_applied_and_recorded():
    info = describe_plugins(refresh=True)
    names = {item["name"] for item in info}
    assert "SampleHaiku" in names

    ir = compile_text("write a haiku about the autumn sky")

    assert any("haiku" in c.lower() for c in ir.constraints)

    plugin_meta = ir.metadata.get("plugins")
    assert plugin_meta is not None
    applied = plugin_meta.get("applied") or []
    assert any(entry.get("name") == "SampleHaiku" for entry in applied)

    origins = ir.metadata.get("constraint_origins") or {}
    matched = False
    for constraint, origin in origins.items():
        if "haiku" in constraint.lower():
            matched = True
            assert origin == "plugin:SampleHaiku"
    assert matched, "haiku constraint missing origin metadata"
