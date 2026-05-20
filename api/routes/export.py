from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.shared import logger

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
):
    if req.format not in [
        "claude-sdk",
        "claude-agent-sdk-py",
        "claude-agent-sdk-ts",
        "claude-subagent",
        "claude-project-pack",
        "langchain",
        "langchain-yaml",
        "langgraph",
    ]:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    from app.adapters.agent_ir import parse_agent_markdown
    from app.adapters.claude_code import (
        to_agent_sdk_python,
        to_agent_sdk_typescript,
        to_claude_project_pack,
        to_claude_subagent,
    )
    from app.adapters.claude_sdk import to_python, to_yaml
    from app.adapters.langchain import to_langchain_python, to_langgraph_python

    try:
        ir = parse_agent_markdown(req.system_prompt or "")

        python_code = None
        yaml_config = None
        code = None
        files = []

        if req.format == "claude-sdk":
            python_code = to_python(ir)
            code = python_code
            if req.output_type != "python":
                yaml_config = to_yaml(ir)
        elif req.format == "claude-agent-sdk-py":
            python_code = to_agent_sdk_python(ir)
            code = python_code
        elif req.format == "claude-agent-sdk-ts":
            code = to_agent_sdk_typescript(ir)
        elif req.format == "claude-subagent":
            files = [to_claude_subagent(ir)]
            code = files[0]["content"]
        elif req.format == "claude-project-pack":
            files = to_claude_project_pack(ir)
        elif req.format in {"langchain", "langchain-yaml"}:
            python_code = to_langchain_python(ir)
            code = python_code
        elif req.format == "langgraph":
            python_code = to_langgraph_python(ir)
            code = python_code

        if req.output_type == "python":
            yaml_config = None
    except Exception as exc:
        logger.exception("agent export failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc

    return {
        "python_code": python_code,
        "yaml_config": yaml_config,
        "code": code or python_code,
        "files": files,
    }


_SKILL_EXPORT_FORMATS = frozenset(
    {
        "claude-tool",
        "claude-tool-use",
        "claude-mcp-tool-stub",
        "langchain-tool",
        "agent-skill",
    }
)


@router.post("/skills-generator/export")
async def export_skill(
    req: ExportRequest,
):
    if req.format not in _SKILL_EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    from app.adapters.claude_code import to_claude_mcp_tool_stub
    from app.adapters.skill_adapter import (
        to_agent_skill,
        to_claude_tool_use,
        to_langchain_tool,
    )
    from app.adapters.skill_ir import parse_skill_markdown

    try:
        ir = parse_skill_markdown(req.skill_definition or "")

        is_agent_skill = req.format == "agent-skill"
        python_code = None if is_agent_skill else to_langchain_tool(ir)
        json_config = None if is_agent_skill else to_claude_tool_use(ir)
        markdown = to_agent_skill(ir) if is_agent_skill else None
        files: list[dict] = []

        if req.format == "claude-mcp-tool-stub":
            files = to_claude_mcp_tool_stub(ir)
            python_code = files[0]["content"]
    except Exception as exc:
        logger.exception("skill export failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc

    return {
        "python_code": python_code,
        "json_config": json_config,
        "markdown": markdown,
        "code": markdown if is_agent_skill else python_code,
        "files": files,
    }
