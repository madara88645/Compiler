from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app import get_build_info


# Global Hybrid Compiler Instance (Lazy Load)
hybrid_compiler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global hybrid_compiler
    from app.llm_engine.hybrid import HybridCompiler

    hybrid_compiler = HybridCompiler()
    print(f"[BACKEND] HybridCompiler initialized (v{get_build_info()['version']})")
    yield
    # Shutdown logic (if any)


app = FastAPI(title="Prompt Compiler API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    # Allow specific origins from env (comma separated) or default to *
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---
from app.routers.benchmark import router as benchmark_router  # noqa: E402

app.include_router(benchmark_router)
