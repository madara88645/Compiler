"""
skill_adapter.py — Generate framework-specific exports from a SkillExportIR.

Supported targets:
  * LangChain `@tool` Python module (to_langchain_tool)
  * Claude tool_use JSON config       (to_claude_tool_use)
  * Anthropic Agent Skill SKILL.md    (to_agent_skill)
"""
from __future__ import annotations

import json
import re

from .skill_ir import SkillExample, SkillExportIR, SkillParam


def _capitalize_words(snake: str) -> list[str]:
    return [w.capitalize() for w in snake.split("_")]


def _to_pascal(snake: str) -> str:
    return "".join(_capitalize_words(snake))


def _to_kebab(snake: str) -> str:
    """Convert snake_case to kebab-case for SKILL.md frontmatter `name`."""
    return re.sub(r"_+", "-", snake.strip("_")).lower()


def _to_title(snake: str) -> str:
    return " ".join(_capitalize_words(snake))


def _example_value_for(param: SkillParam, examples: list[SkillExample]) -> str | None:
    """
    Best-effort extraction of an example value for `param` from `examples`.
    Looks for `param_name: value` or `param_name="value"` inside the input
    expression. Returns None when nothing confident can be extracted.
    """
    if not examples:
        return None
    name = re.escape(param.name)
    patterns = [
        rf'{name}\s*[:=]\s*"([^"]*)"',
        rf"{name}\s*[:=]\s*'([^']*)'",
        rf"{name}\s*[:=]\s*([^,\s\}}]+)",
    ]
    for ex in examples:
        for pat in patterns:
            m = re.search(pat, ex.input)
            if m:
                return m.group(1).strip().rstrip(",")
    return None


def _resolve_example_map(
    params: list[SkillParam], examples: list[SkillExample]
) -> dict[str, str | None]:
    """Pre-resolve example values for all params in one pass."""
    return {p.name: _example_value_for(p, examples) for p in params}


def _coerce_example(value: str, py_type: str) -> int | float | bool | str:
    """Coerce a raw string to its native Python/JSON type."""
    if py_type == "int":
        try:
            return int(value)
        except ValueError:
            return value
    if py_type == "float":
        try:
            return float(value)
        except ValueError:
            return value
    if py_type == "bool":
        return value.lower() in {"true", "1", "yes"}
    return value


def _python_literal_for(value: str, py_type: str) -> str:
    """Format a string-extracted example as a Python source literal."""
    native = _coerce_example(value, py_type)
    if isinstance(native, bool):
        return "True" if native else "False"
    if isinstance(native, (int, float)):
        return str(native)
    return f'"{native}"'


def _param_field_line(p: SkillParam, example_map: dict[str, str | None]) -> str:
    desc = p.description.replace('"', '\\"')
    example = example_map.get(p.name)
    extra = f", examples=[{_python_literal_for(example, p.type)}]" if example is not None else ""
    if p.required:
        return f'    {p.name}: {p.type} = Field(description="{desc}"{extra})'
    return f'    {p.name}: {p.type} | None = Field(default=None, description="{desc}"{extra})'


def _param_signature(p: SkillParam) -> str:
    opt = " | None = None" if not p.required else ""
    return f"{p.name}: {p.type}{opt}"


def _build_docstring(ir: SkillExportIR) -> str:
    """
    Build the LangChain tool docstring.

    Single-line when only `purpose` is present (preserves backward compat with
    existing call sites and tests). Multi-line block when when_to_use or
    error_handling adds substance.
    """
    purpose = (ir.purpose or f"Execute the {ir.name} skill.").replace('"""', '\\"\\"\\"')

    has_when = bool(ir.when_to_use.strip())
    has_errors = bool(ir.error_handling)

    if not has_when and not has_errors:
        return f'    """{purpose}"""'

    lines = [purpose, ""]
    if has_when:
        when = ir.when_to_use.replace('"""', '\\"\\"\\"')
        lines.append("When to use:")
        lines.append(f"    {when}")
        lines.append("")
    if has_errors:
        lines.append("Errors:")
        for item in ir.error_handling:
            sanitized = item.replace('"""', '\\"\\"\\"')
            lines.append(f"    - {sanitized}")
    while lines and not lines[-1].strip():
        lines.pop()

    body = "\n    ".join(lines)
    return f'    """{body}\n    """'


def to_langchain_tool(ir: SkillExportIR) -> str:
    """Return a LangChain @tool Python definition for this skill."""
    pascal_name = _to_pascal(ir.name)
    func_name = ir.name

    if ir.params:
        example_map = _resolve_example_map(ir.params, ir.examples)
        param_fields = "\n".join(_param_field_line(p, example_map) for p in ir.params)
        input_model = f"class {pascal_name}Input(BaseModel):\n{param_fields}\n"
        schema_arg = f"args_schema={pascal_name}Input"
        sig_params = ", ".join(_param_signature(p) for p in ir.params)
    else:
        input_model = ""
        schema_arg = ""
        sig_params = ""

    decorator = f"@tool({schema_arg})" if schema_arg else "@tool"

    parts = [
        "from langchain.tools import tool",
        "from pydantic import BaseModel, Field",
    ]

    if any(p.type == "Any" for p in ir.params) or ir.output_type == "Any":
        parts.append("from typing import Any")

    parts.append("")

    if input_model:
        parts.append(input_model)

    parts.append(decorator)
    if sig_params:
        parts.append(f"def {func_name}({sig_params}) -> {ir.output_type}:")
    else:
        parts.append(f"def {func_name}() -> {ir.output_type}:")
    parts.append(_build_docstring(ir))
    parts.append("    # TODO: implement")
    parts.append("    pass")

    return "\n".join(parts)


def to_claude_tool_use(ir: SkillExportIR) -> str:
    """Return a Claude tool_use JSON block for this skill."""
    properties: dict = {}
    required: list[str] = []

    example_map = _resolve_example_map(ir.params, ir.examples)
    for p in ir.params:
        prop: dict = {"type": _py_to_json_type(p.type)}
        if p.description:
            prop["description"] = p.description
        example = example_map.get(p.name)
        if example is not None:
            prop["examples"] = [_coerce_example(example, p.type)]
        properties[p.name] = prop
        if p.required:
            required.append(p.name)

    input_schema: dict = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = required

    base_description = ir.purpose or f"Execute the {ir.name} skill."
    description = (
        f"{base_description} {ir.when_to_use}".strip() if ir.when_to_use else base_description
    )

    tool_def = {
        "name": ir.name,
        "description": description,
        "input_schema": input_schema,
    }

    return json.dumps(tool_def, indent=2)


def _py_to_json_type(py_type: str) -> str:
    mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "dict": "object",
        "list": "array",
        "Any": "string",
    }
    return mapping.get(py_type, "string")


_DESC_MAX = 200


def _yaml_safe(value: str) -> str:
    """
    Encode a value safely for a YAML scalar in frontmatter.
    Quotes the value when it contains characters that would break a bare scalar.
    """
    value = value.replace("\r", " ").replace("\n", " ").strip()
    if any(
        ch in value
        for ch in (":", "#", "`", '"', "'", "[", "]", "{", "}", "&", "*", "!", "|", ">", "%", "@")
    ):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _truncate_at_sentence(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx >= max_len // 2:
            return cut[: idx + 1].strip()
    last_space = cut.rfind(" ")
    if last_space >= max_len // 2:
        return cut[:last_space].rstrip(",;:") + "…"
    return cut.rstrip() + "…"


def _build_description(ir: SkillExportIR) -> str:
    parts: list[str] = []
    if ir.purpose:
        parts.append(ir.purpose.strip().rstrip("."))
    if ir.when_to_use:
        parts.append(ir.when_to_use.strip().rstrip("."))
    if not parts:
        return f"Skill {ir.name}"
    joined = ". ".join(parts) + "."
    return _truncate_at_sentence(joined, _DESC_MAX)


def _render_inputs_block(ir: SkillExportIR) -> str:
    if not ir.params:
        return "_No inputs._"
    example_map = _resolve_example_map(ir.params, ir.examples)
    lines: list[str] = []
    for p in ir.params:
        required = "required" if p.required else "optional"
        desc = p.description.strip() or "(no description)"
        line = f"- `{p.name}` (`{p.type}`, {required}): {desc}"
        example = example_map.get(p.name)
        if example is not None:
            line += f"  _Example: `{example}`._"
        lines.append(line)
    return "\n".join(lines)


def _render_examples_block(examples: list[SkillExample]) -> str:
    if not examples:
        return ""
    lines = ["## Examples", ""]
    for ex in examples:
        lines.append(f"- Input: `{ex.input}` → Output: `{ex.output}`")
    return "\n".join(lines)


def _render_bullets_block(title: str, items: list[str]) -> str:
    if not items:
        return ""
    lines = [f"## {title}", ""]
    for it in items:
        lines.append(f"- {it}")
    return "\n".join(lines)


def to_agent_skill(ir: SkillExportIR) -> str:
    """
    Render an Anthropic Agent Skill (SKILL.md) from the IR.

    Conforms to the public Skills format:
      * YAML frontmatter with `name` (lowercase, hyphens) and `description`
        (third-person, ≤~200 chars, includes both *what* and *when*).
      * Body uses the canonical headings consumers look for.
      * Empty sections are omitted entirely (no orphaned headings).
    """
    name_kebab = _to_kebab(ir.name) or "skill"
    title = _to_title(ir.name) or "Skill"
    description = _build_description(ir)

    output_block_parts: list[str] = [f"**Type:** `{ir.output_type}`"]
    if ir.output_description.strip():
        output_block_parts.append(ir.output_description.strip())
    output_block = "\n".join(output_block_parts)

    procedure = ir.implementation.strip() or (
        "_No implementation steps were provided. Author this section before publishing._"
    )

    sections: list[str] = [
        "---",
        f"name: {_yaml_safe(name_kebab)}",
        f"description: {_yaml_safe(description)}",
        "---",
        "",
        f"# {title}",
        "",
        "## Overview",
        ir.purpose.strip() or "_No overview provided._",
    ]

    if ir.when_to_use.strip():
        sections += ["", "## When to use this skill", ir.when_to_use.strip()]

    sections += [
        "",
        "## Inputs",
        _render_inputs_block(ir),
        "",
        "## Output",
        output_block,
        "",
        "## Procedure",
        procedure,
    ]

    for block in (
        _render_examples_block(ir.examples),
        _render_bullets_block("Error handling", ir.error_handling),
        _render_bullets_block("Performance notes", ir.performance_notes),
        _render_bullets_block("Testing strategy", ir.testing_strategy),
        _render_bullets_block("Dependencies", ir.dependencies),
    ):
        if block:
            sections += ["", block]

    sections.append("")
    return "\n".join(sections)
