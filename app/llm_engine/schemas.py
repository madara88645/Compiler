from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from app.models_v2 import IRv2


class DiagnosticItem(BaseModel):
    """Flexible diagnostic - accepts any severity/category."""
    severity: str = "info"
    message: str
    suggestion: Optional[str] = None
    category: str = "general"
    
    model_config = ConfigDict(extra="ignore")


class WorkerResponse(BaseModel):
    """
    Full response from DeepSeek Worker LLM.
    Includes IR structure AND direct prompt outputs.
    """
    ir: IRv2 = Field(..., description="Structured IR of the prompt")
    diagnostics: List[DiagnosticItem] = Field(default_factory=list)
    thought_process: str = Field(default="", description="Chain-of-thought reasoning")
    optimized_content: str = Field(default="", description="Expanded prompt (legacy or auto-generated)")
    
    # NEW: Direct prompt outputs (DeepSeek generates these)
    system_prompt: str = Field(default="", description="Ready-to-use system prompt")
    user_prompt: str = Field(default="", description="Ready-to-use user message")
    plan: str = Field(default="", description="Step-by-step plan/approach")
    
    model_config = ConfigDict(extra="ignore")


class QualityReport(BaseModel):
    """Quality Coach analysis result from DeepSeek."""
    score: int = Field(default=50, ge=0, le=100, description="Overall quality score 0-100")
    category_scores: dict = Field(default_factory=lambda: {"clarity": 0, "specificity": 0, "completeness": 0, "consistency": 0}, description="Score breakdown by category")
    strengths: List[str] = Field(default_factory=list, description="What's good about the prompt")
    weaknesses: List[str] = Field(default_factory=list, description="What needs improvement")
    suggestions: List[str] = Field(default_factory=list, description="Actionable improvements")
    summary: str = Field(default="", description="Brief overall assessment")
    
    model_config = ConfigDict(extra="ignore")


class LLMFixResponse(BaseModel):
    """Auto-fix result from DeepSeek Editor."""
    fixed_text: str = Field(..., description="The improved prompt text")
    explanation: str = Field(default="", description="What changed and why")
    changes: List[str] = Field(default_factory=list, description="List of specific changes applied")

    model_config = ConfigDict(extra="ignore")
