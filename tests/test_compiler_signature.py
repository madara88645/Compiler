"""Tests for app.compiler._compute_signature: a pure, deterministic hash of
the IR fields that determine cache/dedup identity. Only exercised indirectly
today (via optimize_ir), so its own determinism and sensitivity to each
tracked field has no direct assertions.
"""

import re

from app.compiler import _compute_signature
from app.models import IR


def _make_ir(**overrides):
    defaults = dict(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        output_format="markdown",
        length_hint="medium",
        metadata={},
    )
    defaults.update(overrides)
    return IR(**defaults)


def test_signature_is_a_16_char_hex_string():
    signature = _compute_signature(_make_ir())
    assert re.fullmatch(r"[0-9a-f]{16}", signature)


def test_signature_is_deterministic_for_identical_ir_content():
    ir_a = _make_ir(goals=["a", "b"], tasks=["t1"], constraints=["c1"])
    ir_b = _make_ir(goals=["a", "b"], tasks=["t1"], constraints=["c1"])
    assert _compute_signature(ir_a) == _compute_signature(ir_b)


def test_signature_changes_when_goals_differ():
    ir_a = _make_ir(goals=["a"])
    ir_b = _make_ir(goals=["b"])
    assert _compute_signature(ir_a) != _compute_signature(ir_b)


def test_signature_changes_when_domain_differs():
    ir_a = _make_ir(domain="general")
    ir_b = _make_ir(domain="coding")
    assert _compute_signature(ir_a) != _compute_signature(ir_b)


def test_signature_changes_when_heuristic_version_metadata_differs():
    ir_a = _make_ir(metadata={"heuristic_version": 1})
    ir_b = _make_ir(metadata={"heuristic_version": 2})
    assert _compute_signature(ir_a) != _compute_signature(ir_b)


def test_signature_is_insensitive_to_fields_it_does_not_track():
    # output_format/length_hint/role/style are intentionally excluded from
    # the signature payload; changing them must not change the signature.
    ir_a = _make_ir(output_format="markdown", length_hint="medium", role="A")
    ir_b = _make_ir(output_format="text", length_hint="short", role="B")
    assert _compute_signature(ir_a) == _compute_signature(ir_b)


def test_signature_is_order_sensitive_for_list_fields():
    # Signature payload sorts dict keys but not list contents, so goal order matters.
    ir_a = _make_ir(goals=["a", "b"])
    ir_b = _make_ir(goals=["b", "a"])
    assert _compute_signature(ir_a) != _compute_signature(ir_b)
