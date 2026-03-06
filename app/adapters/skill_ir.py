"""
skill_ir.py — Parse Skills Generator markdown output into a structured IR.

Skills Generator output has sections: Name, Purpose, Input Schema, Output Schema,
Implementation, Dependencies, Error Handling, Implementation Example (optional).
"""
from __future__ import annotations

import re
from pydantic import BaseModel, Field


class SkillParam(BaseModel):
    name: str
    type: str = "str"
    description: str = ""
    required: bool = True


class SkillExportIR(BaseModel):
    name: str = "skill_name"  # snake_case from ## Name
    purpose: str = ""  # from ## Purpose
    params: list[SkillParam] = Field(default_factory=list)  # from ## Input Schema
    output_type: str = "str"  # inferred from ## Output Schema
    output_description: str = ""
    dependencies: list[str] = Field(default_factory=list)  # from ## Dependencies
    raw_definition: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_section(text: str) -> str:
    return text.strip()


def _extract_sections(markdown: str) -> dict[str, str]:
    """Split markdown into {lower_header: content}."""
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip().lower()
            current_lines = []
        elif line.startswith("# ") and not line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
                current_key = None
                current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            title = re.sub(
                r"\s*[-–]\s*(skill\s+definition|definition|skill)$",
                "",
                title,
                flags=re.IGNORECASE,
            )
            return title.strip()
    return "skill_name"


def _to_snake(name: str) -> str:
    # Preserve underscores — they are valid in snake_case identifiers
    s = re.sub(r"[^a-zA-Z0-9_\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip()).lower()
    return s or "skill_name"


def _parse_name_section(text: str) -> str:
    """Extract snake_case name from ## Name section."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            # Already snake_case most of the time
            return _to_snake(stripped.split()[0])
    return ""


def _parse_params(text: str) -> list[SkillParam]:
    """
    Parse ## Input Schema into SkillParam list.
    Handles both markdown table format and bullet list format.
    """
    params: list[SkillParam] = []

    # Try table format: | Name | Type | Description | Required |
    table_rows = re.findall(
        r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|(?:\s*([^|]+?)\s*\|)?",
        text,
        re.MULTILINE,
    )
    if len(table_rows) > 1:  # >1 because first row is header
        for row in table_rows[1:]:
            name_cell = row[0].strip()
            type_cell = row[1].strip()
            desc_cell = row[2].strip()
            req_cell = row[3].strip().lower() if len(row) > 3 else "yes"
            if name_cell.lower() in ("name", "parameter", "param", "---", "-"):
                continue
            if re.match(r"^-+$", name_cell):
                continue
            params.append(
                SkillParam(
                    name=_to_snake(name_cell),
                    type=_normalise_type(type_cell),
                    description=desc_cell,
                    required="no" not in req_cell and "false" not in req_cell,
                )
            )
        if params:
            return params

    # Fallback: bullet list  "- param_name (type): description"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            content = stripped[2:].strip()
            # Pattern: name (type): description
            m = re.match(r"^(\w+)\s*\(([^)]+)\)\s*:?\s*(.*)", content)
            if m:
                params.append(
                    SkillParam(
                        name=_to_snake(m.group(1)),
                        type=_normalise_type(m.group(2)),
                        description=m.group(3).strip(),
                    )
                )
            else:
                # Plain bullet: treat as str param
                name = _to_snake(content.split(":")[0].split(" ")[0])
                if name:
                    params.append(SkillParam(name=name))

    return params


def _parse_output_type(text: str) -> tuple[str, str]:
    """Infer output type from ## Output Schema text. Returns (type, description)."""
    text_lower = text.lower()
    type_map = [
        (["dict", "json", "object", "map"], "dict"),
        (["list", "array"], "list"),
        (["bool", "boolean", "true/false"], "bool"),
        (["int", "integer", "number", "count"], "int"),
        (["float", "decimal"], "float"),
    ]
    for keywords, py_type in type_map:
        if any(kw in text_lower for kw in keywords):
            return py_type, text.strip()
    return "str", text.strip()


def _parse_dependencies(text: str) -> list[str]:
    deps: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            dep = stripped[2:].strip()
            if dep:
                deps.append(dep)
    return deps


def _normalise_type(raw: str) -> str:
    """Map common type strings to Python type hints."""
    mapping = {
        "string": "str",
        "text": "str",
        "integer": "int",
        "number": "int",
        "float": "float",
        "double": "float",
        "boolean": "bool",
        "bool": "bool",
        "list": "list",
        "array": "list",
        "dict": "dict",
        "object": "dict",
        "json": "dict",
        "any": "Any",
    }
    return mapping.get(raw.strip().lower(), raw.strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_skill_markdown(markdown: str) -> SkillExportIR:
    """Parse Skills Generator markdown output into SkillExportIR."""
    markdown = markdown.strip()
    sections = _extract_sections(markdown)

    raw_name = sections.get("name", "")
    parsed_name = _parse_name_section(raw_name) if raw_name else _to_snake(_extract_title(markdown))

    output_type, output_desc = _parse_output_type(sections.get("output schema", ""))

    return SkillExportIR(
        name=parsed_name or "skill_name",
        purpose=_clean_section(sections.get("purpose", "")),
        params=_parse_params(sections.get("input schema", "")),
        output_type=output_type,
        output_description=output_desc,
        dependencies=_parse_dependencies(sections.get("dependencies", "")),
        raw_definition=markdown,
    )
