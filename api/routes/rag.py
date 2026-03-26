from __future__ import annotations

import functools
from typing import List, Optional

import anyio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key, verify_api_key_if_required
from api.shared import logger
from app.rag.simple_index import (
    ingest_paths,
    pack as rag_pack_ctx,
    search as rag_search,
    search_embed as rag_search_embed,
    search_hybrid as rag_search_hybrid,
    stats as rag_stats,
)
from app.rag.uploads import (
    PathSecurityError,
    get_allowed_roots,
    normalize_display_name,
    resolve_allowed_path,
    store_uploaded_text,
)

router = APIRouter(tags=["rag"])


class RagIngestRequest(BaseModel):
    paths: List[str] = Field(..., min_length=1, max_length=50)
    exts: Optional[List[str]] = Field(default=None, max_length=25)
    embed: bool = Field(default=False)
    embed_dim: int = Field(default=64, ge=8, le=1024)
    chunking_strategy: str = Field(default="paragraph", pattern="^(fixed|paragraph|semantic)$")


class RagIngestResponse(BaseModel):
    ingested_docs: int
    total_chunks: int
    elapsed_ms: int


class RagUploadRequest(BaseModel):
    filename: str = Field(default="upload.txt", max_length=255)
    content: str = Field(..., min_length=1, max_length=1_000_000)
    embed: bool = Field(default=False)
    embed_dim: int = Field(default=64, ge=8, le=1024)
    force: bool = Field(default=False)


class RagUploadResponse(RagIngestResponse):
    filename: str
    success: bool = True
    num_chunks: int
    message: str


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    k: int = Field(default=5, ge=1, le=20)
    method: str = Field(default="fts", pattern="^(fts|embed|hybrid)$")
    embed_dim: int = Field(default=64, ge=8, le=1024)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)


class RagQueryResponse(BaseModel):
    results: List[dict]
    count: int


class RagPackRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    k: int = Field(default=5, ge=1, le=20)
    method: str = Field(default="fts", pattern="^(fts|embed|hybrid)$")
    embed_dim: int = Field(default=64, ge=8, le=1024)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    max_chars: int = Field(default=4000, ge=1, le=20_000)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8_000)
    token_ratio: float = Field(default=4.0, gt=0, le=20.0)
    dedup: bool = False
    token_aware: bool = False


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=20)


class RagSearchResult(BaseModel):
    path: str
    snippet: str
    score: float


def _canonical_search_result(item: dict) -> dict:
    return {
        "path": item.get("path", ""),
        "snippet": item.get("snippet", ""),
        "score": float(item.get("score", 0.0) or 0.0),
    }


def _secure_ingest_paths(paths: list[str]) -> list[str]:
    roots = get_allowed_roots()
    resolved_paths: list[str] = []

    for raw_path in paths:
        resolved = resolve_allowed_path(raw_path, allowed_roots=roots)
        if not resolved.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {resolved}")
        resolved_paths.append(str(resolved))

    return resolved_paths


@router.post("/rag/ingest", response_model=RagIngestResponse)
async def rag_ingest(
    req: RagIngestRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    try:
        secure_paths = _secure_ingest_paths(req.paths)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    docs, chunks, secs = await anyio.to_thread.run_sync(
        functools.partial(
            ingest_paths,
            secure_paths,
            exts=req.exts,
            embed=req.embed,
            embed_dim=req.embed_dim,
            chunking_strategy=req.chunking_strategy,
            allowed_roots=get_allowed_roots(),
        )
    )
    return RagIngestResponse(ingested_docs=docs, total_chunks=chunks, elapsed_ms=int(secs * 1000))


@router.post("/rag/query", response_model=RagQueryResponse)
async def rag_query(
    req: RagQueryRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    if req.method == "embed":
        results = rag_search_embed(req.query, k=req.k, embed_dim=req.embed_dim)
    elif req.method == "hybrid":
        results = rag_search_hybrid(
            req.query,
            k=req.k,
            embed_dim=req.embed_dim,
            alpha=req.alpha,
        )
    else:
        results = rag_search(req.query, k=req.k)
    return RagQueryResponse(results=results, count=len(results))


@router.post("/rag/pack")
async def rag_pack(
    req: RagPackRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key

    if req.method == "embed":
        results = rag_search_embed(req.query, k=req.k, embed_dim=req.embed_dim)
    elif req.method == "hybrid":
        results = rag_search_hybrid(
            req.query,
            k=req.k,
            embed_dim=req.embed_dim,
            alpha=req.alpha,
        )
    else:
        results = rag_search(req.query, k=req.k)

    return rag_pack_ctx(
        req.query,
        results,
        max_chars=req.max_chars,
        max_tokens=req.max_tokens,
        token_chars=req.token_ratio,
        dedup=req.dedup,
        token_aware=req.token_aware,
    )


@router.post("/rag/upload", response_model=RagUploadResponse)
async def rag_upload(
    req: RagUploadRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key

    try:
        stored_path, display_name = await anyio.to_thread.run_sync(
            functools.partial(store_uploaded_text, req.filename, req.content)
        )
        docs, chunks, secs = await anyio.to_thread.run_sync(
            functools.partial(
                ingest_paths,
                [str(stored_path)],
                embed=req.embed,
                embed_dim=req.embed_dim,
                allowed_roots=get_allowed_roots(),
            )
        )
        return RagUploadResponse(
            filename=normalize_display_name(display_name),
            ingested_docs=docs,
            total_chunks=chunks,
            elapsed_ms=int(secs * 1000),
            num_chunks=chunks,
            message=f"Indexed {normalize_display_name(display_name)} into the RAG index.",
        )
    except Exception as exc:
        logger.exception("rag upload failed")
        raise HTTPException(status_code=500, detail="Failed to upload and index content.") from exc


@router.get("/rag/stats")
async def rag_stats_endpoint(
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    return rag_stats()


@router.post("/rag/search", response_model=List[RagSearchResult])
async def rag_search_endpoint(
    req: RagSearchRequest,
    api_key: APIKey | None = Depends(verify_api_key_if_required),
):
    del api_key
    return [_canonical_search_result(item) for item in rag_search(req.query, k=req.limit)]
