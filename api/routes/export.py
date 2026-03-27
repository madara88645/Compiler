from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key_if_required

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    system_prompt: Optional[str] = Field(default=None, max_length=30_000)
    skill_definition: Optional[str] = Field(default=None, max_length=30_000)
    format: str = Field(..., min_length=1, max_length=100)
    output_type: str = Field(default="python", max_length=50)
    is_multi_agent: bool = False


@router.post("/agent-generator/export")
async def export_agent(
    req: ExportRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    if req.format not in ["claude-sdk", "langchain", "langchain-yaml", "langgraph"]:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    from app.adapters.agent_ir import parse_agent_markdown
    from app.adapters.claude_sdk import to_python, to_yaml
    from app.adapters.langchain import to_langchain_python, to_langgraph_python

    ir = parse_agent_markdown(req.system_prompt or "")

    python_code = None
    yaml_config = None

    if req.format == "claude-sdk":
        python_code = to_python(ir)
        if req.output_type != "python":
            yaml_config = to_yaml(ir)
    elif req.format in {"langchain", "langchain-yaml"}:
        python_code = to_langchain_python(ir)
    elif req.format == "langgraph":
        python_code = to_langgraph_python(ir)

    if req.output_type == "python":
        yaml_config = None

    return {
        "python_code": python_code,
        "yaml_config": yaml_config,
        "code": python_code,
        "files": [],
    }


@router.post("/skills-generator/export")
async def export_skill(
    req: ExportRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    if req.format not in ["claude-tool", "langchain-tool"]:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    from app.adapters.skill_adapter import to_claude_tool_use, to_langchain_tool
    from app.adapters.skill_ir import parse_skill_markdown

    ir = parse_skill_markdown(req.skill_definition or "")

    python_code = to_langchain_tool(ir)
    json_config = to_claude_tool_use(ir)

    return {
        "python_code": python_code,
        "json_config": json_config,
        "code": python_code,
        "files": [],
    }
