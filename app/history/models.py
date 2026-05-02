from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HistoryEntry(BaseModel):
    id: str = Field(..., max_length=100)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    prompt_text: str = Field(..., max_length=30000)
    source: str = Field(default="user", max_length=50)  # user, optimizer, system, import
    parent_id: Optional[str] = Field(default=None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = None
