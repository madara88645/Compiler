"""Packaged resources (schemas, templates).

This module centralizes access to files that must work both in a git checkout
and when installed from PyPI (where relative paths like ./schema/... will not
exist).
"""

from __future__ import annotations

import json
from importlib import resources


def _read_app_text(rel_path: str) -> str:
    return resources.files("app").joinpath(rel_path).read_text(encoding="utf-8")


def get_ir_schema_text(*, v2: bool) -> str:
    """Return IR JSON schema as text."""
    filename = "ir_v2.schema.json" if v2 else "ir.schema.json"
    return _read_app_text(f"_schemas/{filename}")


def get_ir_schema_json(*, v2: bool) -> dict:
    """Return IR JSON schema parsed into a dict."""
    return json.loads(get_ir_schema_text(v2=v2))


def iter_builtin_template_texts() -> list[tuple[str, str]]:
    """Yield (name, text) for built-in template YAML files shipped in the package."""
    out: list[tuple[str, str]] = []
    root = resources.files("app").joinpath("_builtin_templates")
    for entry in root.iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            out.append((entry.name, entry.read_text(encoding="utf-8")))
    return sorted(out, key=lambda t: t[0])
