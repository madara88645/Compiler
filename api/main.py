from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import get_build_info

from api.shared import is_meta_leaked, logger

# Global Hybrid Compiler Instance (Lazy Load)
hybrid_compiler = None

# Backwards-compatibility export for tests and legacy imports.
_is_meta_leaked = is_meta_leaked


def get_compiler():
    global hybrid_compiler
    if hybrid_compiler is None:
        from app.llm_engine.hybrid import HybridCompiler

        hybrid_compiler = HybridCompiler()
    return hybrid_compiler


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_compiler()
    logger.info("HybridCompiler initialized", extra={"version": get_build_info()["version"]})
    yield


app = FastAPI(title="Prompt Compiler API", lifespan=lifespan)


allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
allow_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
if not allow_origins:
    allow_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers[
        "Content-Security-Policy"
    ] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com"
    return response


from api.routes.compile import router as compile_router  # noqa: E402
from api.routes.export import router as export_router  # noqa: E402
from api.routes.generators import router as generators_router  # noqa: E402
from api.routes.meta import router as meta_router  # noqa: E402
from api.routes.rag import router as rag_router  # noqa: E402
from app.routers.benchmark import router as benchmark_router  # noqa: E402
from app.routers.jules import router as jules_router  # noqa: E402

app.include_router(meta_router)
app.include_router(compile_router)
app.include_router(generators_router)
app.include_router(export_router)
app.include_router(rag_router)
app.include_router(benchmark_router)
app.include_router(jules_router)
