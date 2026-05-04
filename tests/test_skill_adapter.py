import json
import re

import yaml

from app.adapters.skill_adapter import (
    _to_pascal,
    _py_to_json_type,
    to_agent_skill,
    to_claude_tool_use,
    to_langchain_tool,
)
from app.adapters.skill_ir import SkillExample, SkillExportIR, SkillParam


def test_to_pascal():
    assert _to_pascal("hello_world") == "HelloWorld"
    assert _to_pascal("my_skill_name") == "MySkillName"
    assert _to_pascal("single") == "Single"


def test_py_to_json_type():
    assert _py_to_json_type("str") == "string"
    assert _py_to_json_type("int") == "integer"
    assert _py_to_json_type("float") == "number"
    assert _py_to_json_type("bool") == "boolean"
    assert _py_to_json_type("dict") == "object"
    assert _py_to_json_type("list") == "array"
    assert _py_to_json_type("Any") == "string"
    assert _py_to_json_type("unknown") == "string"


def test_to_langchain_tool_no_params():
    ir = SkillExportIR(
        name="get_weather", purpose="Get the current weather.", params=[], output_type="str"
    )
    result = to_langchain_tool(ir)

    assert "from langchain.tools import tool" in result
    assert "from pydantic import BaseModel, Field" in result
    assert "class GetWeatherInput(BaseModel):" not in result
    assert "@tool" in result
    assert "@tool(" not in result
    assert "def get_weather() -> str:" in result
    assert '"""Get the current weather."""' in result


def test_to_langchain_tool_with_params():
    ir = SkillExportIR(
        name="get_weather",
        purpose='Get the "current" weather.',
        params=[
            SkillParam(
                name="location", type="str", description='City name "or" zip code', required=True
            ),
            SkillParam(
                name="unit", type="str", description="Celsius or Fahrenheit", required=False
            ),
        ],
        output_type="dict",
    )
    result = to_langchain_tool(ir)

    assert "class GetWeatherInput(BaseModel):" in result
    assert 'location: str = Field(description="City name \\"or\\" zip code")' in result
    assert 'unit: str | None = Field(default=None, description="Celsius or Fahrenheit")' in result
    assert "@tool(args_schema=GetWeatherInput)" in result
    assert "def get_weather(location: str, unit: str | None = None) -> dict:" in result
    # The actual tool replacement does not replace double quotes with backslash double quotes if purpose has triple quotes
    # The code does `ir.purpose.replace('"""', '\\"\\"\\"')`. It handles triple quotes, not double quotes.
    assert '"""Get the "current" weather."""' in result


def test_to_langchain_tool_with_any_type():
    ir = SkillExportIR(
        name="process_data",
        purpose="Process arbitrary data",
        params=[
            SkillParam(name="data", type="Any", description="The data", required=True),
        ],
        output_type="Any",
    )
    result = to_langchain_tool(ir)

    assert "from typing import Any" in result
    assert "data: Any = Field(" in result
    assert "def process_data(data: Any) -> Any:" in result


def test_to_claude_tool_use_no_params():
    ir = SkillExportIR(
        name="get_weather", purpose="Get the current weather.", params=[], output_type="str"
    )
    result = to_claude_tool_use(ir)
    data = json.loads(result)

    assert data["name"] == "get_weather"
    assert data["description"] == "Get the current weather."
    assert data["input_schema"] == {"type": "object", "properties": {}}
    assert "required" not in data["input_schema"]


def test_to_claude_tool_use_with_params():
    ir = SkillExportIR(
        name="get_weather",
        purpose="Get the current weather.",
        params=[
            SkillParam(name="location", type="str", description="City name", required=True),
            SkillParam(name="unit", type="str", description="Unit", required=False),
            SkillParam(name="count", type="int", description="", required=True),
        ],
        output_type="str",
    )
    result = to_claude_tool_use(ir)
    data = json.loads(result)

    assert data["name"] == "get_weather"
    assert data["description"] == "Get the current weather."
    assert data["input_schema"]["type"] == "object"

    props = data["input_schema"]["properties"]
    assert props["location"] == {"type": "string", "description": "City name"}
    assert props["unit"] == {"type": "string", "description": "Unit"}
    assert props["count"] == {"type": "integer"}  # no description key

    assert data["input_schema"]["required"] == ["location", "count"]


# ---------------------------------------------------------------------------
# Enriched LangChain docstring (when_to_use + error_handling)
# ---------------------------------------------------------------------------


def test_langchain_tool_keeps_legacy_single_line_docstring():
    """Skills with only a purpose still emit the original single-line docstring."""
    ir = SkillExportIR(name="get_weather", purpose="Get the current weather.")
    result = to_langchain_tool(ir)
    assert '"""Get the current weather."""' in result


def test_langchain_tool_multi_line_docstring_with_when_and_errors():
    ir = SkillExportIR(
        name="fetch_user",
        purpose="Fetch a user record.",
        when_to_use="Use when the agent has a user_id and needs the matching profile.",
        error_handling=[
            "Return None when user_id is missing from the database",
            "Raise ConnectionError when the upstream service is unreachable",
        ],
    )
    result = to_langchain_tool(ir)
    assert "When to use:" in result
    assert "Errors:" in result
    assert "Return None when user_id is missing" in result
    assert "Use when the agent has a user_id" in result


def test_langchain_tool_field_examples_when_provided():
    ir = SkillExportIR(
        name="get_weather",
        purpose="Get current weather.",
        params=[SkillParam(name="city", type="str", description="City name", required=True)],
        examples=[SkillExample(input='{city: "Paris"}', output="22C")],
    )
    result = to_langchain_tool(ir)
    assert 'examples=["Paris"]' in result


# ---------------------------------------------------------------------------
# Claude tool_use examples
# ---------------------------------------------------------------------------


def test_claude_tool_use_includes_when_to_use_in_description():
    ir = SkillExportIR(
        name="search",
        purpose="Search the web.",
        when_to_use="Use when the agent needs fresh information.",
    )
    parsed = json.loads(to_claude_tool_use(ir))
    assert "Search the web." in parsed["description"]
    assert "Use when the agent needs fresh information." in parsed["description"]


def test_claude_tool_use_param_examples_populated():
    ir = SkillExportIR(
        name="fetch_record",
        purpose="Fetch a record.",
        params=[
            SkillParam(name="user_id", type="int", description="User ID", required=True),
            SkillParam(name="city", type="str", description="City name", required=False),
        ],
        examples=[
            SkillExample(input='{user_id: 42, city: "Tokyo"}', output="{...}"),
        ],
    )
    parsed = json.loads(to_claude_tool_use(ir))
    props = parsed["input_schema"]["properties"]
    assert props["user_id"]["examples"] == [42]
    assert props["city"]["examples"] == ["Tokyo"]


def test_claude_tool_use_skips_examples_when_unmappable():
    ir = SkillExportIR(
        name="noop",
        purpose="No-op.",
        params=[SkillParam(name="payload", type="str", description="Payload", required=True)],
        examples=[SkillExample(input="opaque blob", output="result")],
    )
    parsed = json.loads(to_claude_tool_use(ir))
    assert "examples" not in parsed["input_schema"]["properties"]["payload"]


# ---------------------------------------------------------------------------
# Agent Skill (SKILL.md) export
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _frontmatter(skill_md: str) -> dict:
    m = _FRONTMATTER_RE.match(skill_md)
    assert m is not None, "SKILL.md must start with YAML frontmatter"
    return yaml.safe_load(m.group(1))


def test_to_agent_skill_minimal_frontmatter_is_valid_yaml():
    ir = SkillExportIR(
        name="json_validator",
        purpose="Validates JSON documents against a schema.",
        when_to_use="Use when an agent receives JSON and must verify shape before processing.",
    )
    skill_md = to_agent_skill(ir)
    fm = _frontmatter(skill_md)

    assert fm["name"] == "json-validator"
    assert isinstance(fm["description"], str)
    assert "Validates JSON" in fm["description"]
    assert "Use when" in fm["description"] or "use when" in fm["description"].lower()
    assert len(fm["description"]) <= 200


def test_to_agent_skill_renders_canonical_sections():
    ir = SkillExportIR(
        name="weather_lookup",
        purpose="Looks up the current weather for a city.",
        when_to_use="Use when a user asks about current conditions for a place.",
        params=[
            SkillParam(name="city", type="str", description="City name", required=True),
            SkillParam(
                name="unit", type="str", description="celsius or fahrenheit", required=False
            ),
        ],
        output_type="dict",
        output_description="A dict with `temp` and `conditions`.",
        dependencies=["httpx"],
        error_handling=["Raise on network failure", "Return None for unknown cities"],
        performance_notes=["Cache responses for 60s"],
        examples=[SkillExample(input='{city: "Paris"}', output='{"temp": 22}')],
        implementation="1. Call API\n2. Parse response\n3. Return dict",
    )
    skill_md = to_agent_skill(ir)

    # Canonical headings
    assert "# Weather Lookup" in skill_md
    assert "## Overview" in skill_md
    assert "## When to use this skill" in skill_md
    assert "## Inputs" in skill_md
    assert "## Output" in skill_md
    assert "## Procedure" in skill_md
    assert "## Examples" in skill_md
    assert "## Error handling" in skill_md
    assert "## Performance notes" in skill_md
    assert "## Dependencies" in skill_md

    # Inputs render type + required + description
    assert "`city` (`str`, required)" in skill_md
    assert "`unit` (`str`, optional)" in skill_md

    # Output declares the type explicitly
    assert "**Type:** `dict`" in skill_md

    # Procedure is included verbatim
    assert "1. Call API" in skill_md


def test_to_agent_skill_omits_empty_sections():
    ir = SkillExportIR(
        name="bare_skill",
        purpose="Does a thing.",
        when_to_use="Use when needed.",
    )
    skill_md = to_agent_skill(ir)

    assert "## Examples" not in skill_md
    assert "## Error handling" not in skill_md
    assert "## Performance notes" not in skill_md
    assert "## Dependencies" not in skill_md
    assert "## Testing strategy" not in skill_md


def test_to_agent_skill_name_is_kebab_lowercase():
    ir = SkillExportIR(name="multi_word_skill_name", purpose="x")
    fm = _frontmatter(to_agent_skill(ir))
    assert fm["name"] == "multi-word-skill-name"


def test_to_agent_skill_description_truncates_at_sentence():
    long_purpose = (
        "This skill performs an exhaustive sequence of operations on the input payload "
        "to produce a fully validated result that downstream agents can rely on. "
        "It also performs many other things that should be irrelevant to discovery."
    )
    ir = SkillExportIR(
        name="long_one",
        purpose=long_purpose,
        when_to_use="Use when an agent needs an extensive multi-step validation pipeline.",
    )
    fm = _frontmatter(to_agent_skill(ir))
    assert len(fm["description"]) <= 200
