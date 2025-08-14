from __future__ import annotations
from typing import List, Dict, Any
from pydantic import BaseModel, Field, validator

# Intermediate Representation (IR) model mirroring the JSON Schema.
class IR(BaseModel):
    language: str = Field(..., description="Detected language code: tr|en")
    persona: str = Field(..., description="High-level assistant persona")
    role: str = Field(..., description="Assistant role description")
    domain: str = Field(..., description="Primary domain guess")
    goals: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    inputs: Dict[str, str] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    style: List[str] = Field(default_factory=list)
    tone: List[str] = Field(default_factory=list)
    output_format: str = Field(...)
    length_hint: str = Field(...)
    steps: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    banned: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator(
        'goals','tasks','constraints','style','tone','steps','examples','banned','tools',
        pre=True, each_item=False
    )
    def _norm_list(cls, v):  # type: ignore
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        # Deduplicate preserving order
        seen = set()
        out = []
        for item in v:
            if not item:
                continue
            item2 = item.strip()
            if not item2:
                continue
            if item2.lower() in seen:
                continue
            seen.add(item2.lower())
            out.append(item2)
        return out

    @validator('language')
    def _lang(cls, v):  # type: ignore
        if v not in {"tr", "en"}:
            raise ValueError("language must be 'tr' or 'en'")
        return v

    @validator('output_format')
    def _fmt(cls, v):  # type: ignore
        if v not in {"markdown","json","yaml","table","text"}:
            raise ValueError("invalid output_format")
        return v

    @validator('persona')
    def _persona(cls, v):  # type: ignore
        allowed = {"assistant","teacher","researcher","coach","mentor"}
        if v not in allowed:
            raise ValueError(f"persona must be one of {sorted(allowed)}")
        return v

    @validator('length_hint')
    def _len(cls, v):  # type: ignore
        if v not in {"short","medium","long"}:
            raise ValueError("invalid length_hint")
        return v

    class Config:
        extra = 'forbid'
        allow_mutation = True

DEFAULT_ROLE_TR = "Yardımcı üretken yapay zeka asistanı"
DEFAULT_ROLE_EN = "Helpful generative AI assistant"
