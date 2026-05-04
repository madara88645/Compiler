"""
skill_ir.py — Parse Skills Generator markdown output into a structured IR.

Skills Generator output has sections: Name, Purpose, Input Schema, Output Schema,
Implementation, Dependencies, Examples, Error Handling, Testing Strategy,
Performance Considerations, Implementation Example (optional).
"""
from __future__ import annotations

import re
from pydantic import BaseModel, Field


class SkillParam(BaseModel):
    name: str
    type: str = "str"
    description: str = ""
    required: bool = True


class SkillExample(BaseModel):
    input: str = ""
    output: str = ""


class SkillExportIR(BaseModel):
    name: str = "skill_name"
    purpose: str = ""
    when_to_use: str = ""
    params: list[SkillParam] = Field(default_factory=list)
    output_type: str = "str"
    output_description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    error_handling: list[str] = Field(default_factory=list)
    testing_strategy: list[str] = Field(default_factory=list)
    performance_notes: list[str] = Field(default_factory=list)
    examples: list[SkillExample] = Field(default_factory=list)
    implementation: str = ""
    raw_definition: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_section(text: str) -> str:
    """Remove markdown fences and leading/trailing whitespace."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) > 1 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        elif len(lines) > 0:
            return "\n".join(lines[1:]).strip()
    return text


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
                r"\s{0,50}[-–]\s{0,50}(skill\s{1,50}definition|definition|skill)$",
                "",
                title,
                flags=re.IGNORECASE,
            )
            return title.strip()
    return "skill_name"


def _to_snake(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_\s-]", " ", name)
    s = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = s.replace("-", " ")
    s = re.sub(r"\s+", "_", s.strip()).lower()
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s or "skill_name"


def _parse_name_section(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return _to_snake(stripped.split()[0])
    return ""


def _parse_purpose_block(text: str) -> tuple[str, str]:
    """
    Parse ## Purpose. Recognises:
        **What:** ...
        **When to use:** ...
    Falls back to: whole block in `purpose`, empty `when_to_use`.
    Returns (purpose, when_to_use).
    """
    text = _clean_section(text)
    if not text:
        return "", ""

    current = None
    buf: dict[str, list[str]] = {"what": [], "when": []}

    for line in text.splitlines():
        m = _PURPOSE_LABEL_RE.match(line)
        if m:
            tag = "what" if m.group(1).lower() == "what" else "when"
            current = tag
            rest = m.group(2).strip()
            if rest:
                buf[tag].append(rest)
        elif current is not None:
            buf[current].append(line.rstrip())

    what = " ".join(s.strip() for s in buf["what"] if s.strip()).strip()
    when = " ".join(s.strip() for s in buf["when"] if s.strip()).strip()

    if not what and not when:
        # Legacy single-block purpose — keep it all as the purpose.
        return text.strip(), ""

    return what, when


def _parse_params(text: str) -> list[SkillParam]:
    """Parse ## Input Schema into SkillParam list."""
    params: list[SkillParam] = []

    table_rows = re.findall(
        r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|(?:\s*([^|]+?)\s*\|)?",
        text,
        re.MULTILINE,
    )
    if len(table_rows) > 1:
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

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            content = stripped[2:].strip()
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
                name = _to_snake(content.split(":")[0].split(" ")[0])
                if name:
                    params.append(SkillParam(name=name))

    return params


_TYPE_TAG_RE = re.compile(
    r"\*\*\s*type\s*:?\s*\*\*\s*`?\s*([A-Za-z][A-Za-z0-9_]*)\s*`?",
    re.IGNORECASE,
)


def _parse_output_type(text: str) -> tuple[str, str]:
    r"""
    Infer output type from ## Output Schema text.

    Prefers an explicit ``**Type:** `<token>` `` marker; falls back to
    keyword heuristics on the remaining text. Returns (type, description).
    """
    if not text:
        return "str", ""

    m = _TYPE_TAG_RE.search(text)
    if m:
        explicit = _normalise_type(m.group(1))
        # Strip the type-tag line out of the description for cleanliness.
        desc = _TYPE_TAG_RE.sub("", text, count=1).strip()
        return explicit, desc

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


def _parse_bullet_list(text: str) -> list[str]:
    """Extract `- ` / `* ` bullet items from a markdown block."""
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items


# Backward-compatible alias — older imports use `_parse_dependencies`.
_parse_dependencies = _parse_bullet_list


_PURPOSE_LABEL_RE = re.compile(
    r"^\s*\*\*\s*(what|when(?:\s+to\s+use)?)\s*:?\s*\*\*\s*(.*)$",
    re.IGNORECASE,
)

_EXAMPLE_LINE_RE = re.compile(
    r"input\s*:\s*(?P<input>.+?)\s*(?:→|->|=>)\s*output\s*:\s*(?P<output>.+)$",
    re.IGNORECASE,
)


def _parse_examples(text: str) -> list[SkillExample]:
    """Parse `Input: ... → Output: ...` pairs from ## Examples."""
    examples: list[SkillExample] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            stripped = stripped[2:].strip()
        m = _EXAMPLE_LINE_RE.search(stripped)
        if m:
            examples.append(
                SkillExample(
                    input=m.group("input").strip().strip("`"),
                    output=m.group("output").strip().strip("`"),
                )
            )
    return examples


def _normalise_type(raw: str) -> str:
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

    purpose, when_to_use = _parse_purpose_block(sections.get("purpose", ""))
    output_type, output_desc = _parse_output_type(sections.get("output schema", ""))

    return SkillExportIR(
        name=parsed_name or "skill_name",
        purpose=purpose,
        when_to_use=when_to_use,
        params=_parse_params(sections.get("input schema", "")),
        output_type=output_type,
        output_description=output_desc,
        dependencies=_parse_bullet_list(sections.get("dependencies", "")),
        error_handling=_parse_bullet_list(sections.get("error handling", "")),
        testing_strategy=_parse_bullet_list(sections.get("testing strategy", "")),
        performance_notes=_parse_bullet_list(sections.get("performance considerations", "")),
        examples=_parse_examples(sections.get("examples", "")),
        implementation=_clean_section(sections.get("implementation", "")),
        raw_definition=markdown,
    )
