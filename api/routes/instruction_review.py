from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import rate_limit_by_ip
from app.instruction_review import (
    InstructionReviewRequest,
    InstructionReviewResponse,
    analyze_instruction_review,
)

router = APIRouter(tags=["instruction-review"])


@router.post("/instruction-review/analyze", response_model=InstructionReviewResponse)
async def analyze_instruction_review_endpoint(
    req: InstructionReviewRequest,
    _: None = Depends(rate_limit_by_ip),
) -> InstructionReviewResponse:
    """Analyze submitted instruction text without reading or changing a repository."""
    return analyze_instruction_review(req)


__all__ = ["router", "analyze_instruction_review_endpoint"]
