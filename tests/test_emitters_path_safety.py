"""Path-safety of the v2 system-prompt context rendering.

When local RAG retrieval is enabled (#877, opt-in), retrieved snippets can carry
absolute local filesystem paths. Those paths must not leak into the system prompt
sent to the LLM — only the basename should be shown, matching how the other v2
emitter already renders snippet paths.
"""

from __future__ import annotations

from app.emitters import emit_system_prompt_v2
from app.models_v2 import IRv2


def _ir_with_snippet(path: str) -> IRv2:
    ir = IRv2(
        language="en",
        persona="expert",
        role="tester",
        domain="general",
        output_format="text",
        length_hint="medium",
    )
    ir.metadata["context_snippets"] = [{"path": path, "snippet": "def login():\n    pass"}]
    return ir


def test_system_prompt_v2_does_not_leak_absolute_snippet_path():
    ir = _ir_with_snippet("/Users/dev/private/secret_module.py")
    out = emit_system_prompt_v2(ir)
    # The local absolute path must not leak into the LLM system prompt.
    assert "/Users/" not in out
    # The file is still identified, by basename only.
    assert "secret_module.py" in out


def test_system_prompt_v2_keeps_relative_snippet_path_basename():
    ir = _ir_with_snippet("app/auth.py")
    out = emit_system_prompt_v2(ir)
    assert "auth.py" in out
