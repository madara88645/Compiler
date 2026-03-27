from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/")
async def root():
    return {"message": "Prompt Compiler API is running"}
