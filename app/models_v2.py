from __future__ import annotations
from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field, validator


ConstraintPriority = Literal[10,20,30,40,50,60,65,70,80,90]

class ConstraintV2(BaseModel):
    id: str = Field(..., description="Deterministic id for the constraint")
    text: str = Field(..., description="Constraint text")
    origin: str = Field(..., description="Heuristic source tag")
    priority: ConstraintPriority = Field(40, description="Priority weight (higher first)")
    rationale: Optional[str] = Field(None, description="Optional explanation")

class StepV2(BaseModel):
    type: Literal['task','teach','research','compare','plan'] = 'task'
    text: str

class IRv2(BaseModel):
    version: Literal['2.0'] = '2.0'
    language: Literal['tr','en']
    persona: Literal['assistant','teacher','researcher','coach','mentor']
    role: str
    domain: str
    intents: List[Literal['teaching','summary','compare','variants','recency','risk','code','ambiguous']] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    inputs: Dict[str, str] = Field(default_factory=dict)
    constraints: List[ConstraintV2] = Field(default_factory=list)
    style: List[str] = Field(default_factory=list)
    tone: List[str] = Field(default_factory=list)
    output_format: Literal['markdown','json','yaml','table','text']
    length_hint: Literal['short','medium','long']
    steps: List[StepV2] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    banned: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('constraints', pre=True, each_item=False)
    def _norm_constraints(cls, v):  # type: ignore
        return v or []

    class Config:
        extra = 'forbid'
        allow_mutation = True
