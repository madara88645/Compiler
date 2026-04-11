import json

from app.adapters.skill_adapter import (
    _to_pascal,
    _py_to_json_type,
    to_langchain_tool,
    to_claude_tool_use,
)
from app.adapters.skill_ir import SkillExportIR, SkillParam


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
