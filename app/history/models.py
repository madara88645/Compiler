from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HistoryEntry(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    prompt_text: str
    source: str = "user"  # user, optimizer, system, import
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = None
