from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/workspace-generator", tags=["workspace-generator"])


class WorkspaceGenRequest(BaseModel):
    description: str = Field(..., description="Description of the workspace environment")


class WorkspaceGenResponse(BaseModel):
    markdown_config: str


@router.post("/generate", response_model=WorkspaceGenResponse)
async def generate_workspace_endpoint(req: WorkspaceGenRequest):
    """Generate a comprehensive Workspace Configuration in Markdown."""
    from api.main import hybrid_compiler

    if hybrid_compiler is None:
        raise HTTPException(status_code=503, detail="Compiler not initialized")

    try:
        result = hybrid_compiler.generate_workspace(req.description)
        return WorkspaceGenResponse(markdown_config=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
