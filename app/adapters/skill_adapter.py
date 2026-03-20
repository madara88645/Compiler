"""
skill_adapter.py — Generate LangChain Tool and Claude tool_use JSON from SkillExportIR.
"""
from __future__ import annotations

import json

from .skill_ir import SkillExportIR, SkillParam


def _to_pascal(snake: str) -> str:
    return "".join(word.capitalize() for word in snake.split("_"))


def _param_field_line(p: SkillParam) -> str:
    desc = p.description.replace('"', '\\"')
    if p.required:
        return f'    {p.name}: {p.type} = Field(description="{desc}")'
    return f'    {p.name}: {p.type} | None = Field(default=None, description="{desc}")'


def _param_signature(p: SkillParam) -> str:
    opt = " | None = None" if not p.required else ""
    return f"{p.name}: {p.type}{opt}"


# ---------------------------------------------------------------------------
# LangChain Tool
# ---------------------------------------------------------------------------


def to_langchain_tool(ir: SkillExportIR) -> str:
    """Return a LangChain @tool Python definition for this skill."""
    pascal_name = _to_pascal(ir.name)
    func_name = ir.name

    # Build pydantic input model if there are params
    if ir.params:
        # Build each line with correct 4-space indent already applied — avoids
        # the textwrap.dedent + multi-line f-string interpolation gotcha.
        param_fields = "\n".join(_param_field_line(p) for p in ir.params)
        input_model = f"class {pascal_name}Input(BaseModel):\n{param_fields}\n"
        schema_arg = f"args_schema={pascal_name}Input"
        sig_params = ", ".join(_param_signature(p) for p in ir.params)
    else:
        input_model = ""
        schema_arg = ""
        sig_params = ""

    # Docstring for the tool
    purpose = ir.purpose.replace('"""', '\\"\\"\\"') or f"Execute the {func_name} skill."

    # Decorator
    if schema_arg:
        decorator = f"@tool({schema_arg})"
    else:
        decorator = "@tool"

    # Build full output
    parts = [
        "from langchain.tools import tool",
        "from pydantic import BaseModel, Field",
    ]

    # Add typing import if Any is used
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
    parts.append(f'    """{purpose}"""')
    parts.append("    # TODO: implement")
    parts.append("    pass")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Claude tool_use JSON
# ---------------------------------------------------------------------------


def to_claude_tool_use(ir: SkillExportIR) -> str:
    """Return a Claude tool_use JSON block for this skill."""
    properties: dict = {}
    required: list[str] = []

    for p in ir.params:
        prop: dict = {"type": _py_to_json_type(p.type)}
        if p.description:
            prop["description"] = p.description
        properties[p.name] = prop
        if p.required:
            required.append(p.name)

    input_schema: dict = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = required

    tool_def = {
        "name": ir.name,
        "description": ir.purpose or f"Execute the {ir.name} skill.",
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
