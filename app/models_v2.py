from __future__ import annotations
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from pydantic import field_validator
from pydantic.config import ConfigDict


class DiagnosticItem(BaseModel):
    """Flexible diagnostic - accepts any severity/category."""
    severity: str = "info"
    message: str
    suggestion: Optional[str] = None
    category: str = "general"
    
    model_config = ConfigDict(extra="ignore")


class ConstraintV2(BaseModel):
    """Flexible constraint model - accepts any LLM output."""
    id: str = Field(default="", description="Constraint id")
    text: str = Field(..., description="Constraint text")
    origin: str = Field(default="llm", description="Source tag")
    priority: int = Field(default=40, description="Priority weight")
    rationale: Optional[str] = Field(None, description="Optional explanation")
    
    model_config = ConfigDict(extra="ignore")


class StepV2(BaseModel):
    """Flexible step model."""
    type: str = "task"
    text: str
    
    model_config = ConfigDict(extra="ignore")


class IRv2(BaseModel):
    """
    Flexible IR model - accepts whatever DeepSeek returns.
    No strict Literal types, just plain strings with sensible defaults.
    """
    version: str = "2.0"
    language: str = "en"
    persona: str = "assistant"
    role: str = "AI Assistant"
    domain: str = "general"
    intents: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[ConstraintV2] = Field(default_factory=list)
    style: List[str] = Field(default_factory=list)
    tone: List[str] = Field(default_factory=list)
    output_format: str = "markdown"
    length_hint: str = "medium"
    steps: List[StepV2] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    banned: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    
    # NEW: Diagnostics attached directly to IR for heuristics
    diagnostics: List[DiagnosticItem] = Field(default_factory=list)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("constraints", mode="before")
    def _norm_constraints(cls, v):
        if not v:
            return []
        # Handle both dict and ConstraintV2 objects
        result = []
        for item in v:
            if isinstance(item, dict):
                # Ensure required fields have defaults
                item.setdefault("id", "")
                item.setdefault("origin", "llm")
                item.setdefault("priority", 40)
                result.append(item)
            else:
                result.append(item)
        return result

    @field_validator("steps", mode="before")
    def _norm_steps(cls, v):
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                item.setdefault("type", "task")
                result.append(item)
            else:
                result.append(item)
        return result

    model_config = ConfigDict(extra="ignore")
