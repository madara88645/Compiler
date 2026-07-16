import ipaddress
import logging
import time
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict
import os

from fastapi import HTTPException, Security, status, Request
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import create_engine, Column, String, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Database ---

logger = logging.getLogger("promptc.auth")


def _ensure_private_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


_db_dir = Path(os.environ.get("DB_DIR", ".")).expanduser().resolve()
_db_path = _db_dir / "users.db"
_ensure_private_file(_db_path)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_path}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class APIKey(Base):
    __tablename__ = "api_keys"

    key = Column(String, primary_key=True, index=True)
    owner = Column(String, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(Float, default=time.time)


# Create tables
Base.metadata.create_all(bind=engine)


# --- Security ---
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# In-memory rate limiter: {api_key: [timestamp1, timestamp2, ...]}
# Simple sliding window or fixed window?
# Let's do a simple fixed window or just a list of timestamps with cleanup.
RATE_LIMIT_STORE: Dict[str, list] = {}
RATE_LIMIT_LOCK = Lock()
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10
HEAVY_RATE_LIMIT_MAX_REQUESTS = 2
PUBLIC_HEAVY_RATE_LIMIT = 20
PUBLIC_DEFAULT_RATE_LIMIT = 60
# Benchmark gets its own generous per-IP bucket (no human reaches it; it only
# stops a single IP from draining the global daily pool), decoupled from the
# shared "heavy" bucket so heavy /compile use never blocks benchmarking.
PUBLIC_BENCHMARK_RATE_LIMIT = 30

_rate_limit_cleanup_counter = 0


def _get_route_group(path: str) -> str:
    if path.startswith("/benchmark"):
        return "benchmark"
    heavy_routes = [
        "/compile",
        "/optimize",
        "/run",
        "/agent-generator",
        "/skills-generator",
        "/repo-context",
    ]
    for r in heavy_routes:
        if path.startswith(r):
            return "heavy"
    return "default"


def _get_route_group_and_limit(path: str) -> tuple[str, int]:
    group = _get_route_group(path)
    if group == "heavy":
        return group, HEAVY_RATE_LIMIT_MAX_REQUESTS
    return group, RATE_LIMIT_MAX_REQUESTS


def _public_rate_limit_for(group: str) -> int:
    """Per-IP request budget for a public route group (reads live module constants)."""
    if group == "benchmark":
        return PUBLIC_BENCHMARK_RATE_LIMIT
    if group == "heavy":
        return PUBLIC_HEAVY_RATE_LIMIT
    return PUBLIC_DEFAULT_RATE_LIMIT


# --- Benchmark Denial-of-Wallet backstop -----------------------------------
# /benchmark/run is public (no API key) but triggers server-side LLM calls.
# Per-IP rate limiting can be bypassed by rotating IPs, so we add a global
# daily cap on the total number of benchmark runs across all callers. This is a
# catastrophic backstop, not a normal-traffic limiter: set high enough that a
# legitimate visitor essentially never hits it, while still bounding worst-case
# spend from large-scale abuse. Tunable via BENCHMARK_DAILY_RUN_LIMIT.
DEFAULT_BENCHMARK_DAILY_RUN_LIMIT = 10000
_BENCHMARK_DAILY_LOCK = Lock()
_BENCHMARK_DAILY_STATE = {
    "date": datetime.now(timezone.utc).date().isoformat(),
    "count": 0,
}


def _benchmark_daily_limit() -> int:
    raw = os.environ.get("BENCHMARK_DAILY_RUN_LIMIT", "").strip()
    if not raw:
        return DEFAULT_BENCHMARK_DAILY_RUN_LIMIT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_BENCHMARK_DAILY_RUN_LIMIT
    return value if value > 0 else DEFAULT_BENCHMARK_DAILY_RUN_LIMIT


def reset_benchmark_daily_state() -> None:
    """Reset the global benchmark daily-cap counter (day rollover and tests)."""
    with _BENCHMARK_DAILY_LOCK:
        _BENCHMARK_DAILY_STATE["date"] = datetime.now(timezone.utc).date().isoformat()
        _BENCHMARK_DAILY_STATE["count"] = 0


def enforce_benchmark_daily_cap() -> None:
    """Raise HTTP 429 once the global daily benchmark-run budget is exhausted."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _BENCHMARK_DAILY_LOCK:
        if _BENCHMARK_DAILY_STATE["date"] != today:
            _BENCHMARK_DAILY_STATE["date"] = today
            _BENCHMARK_DAILY_STATE["count"] = 0

        if _BENCHMARK_DAILY_STATE["count"] >= _benchmark_daily_limit():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily benchmark limit reached. Please try again tomorrow.",
            )

        _BENCHMARK_DAILY_STATE["count"] += 1


def _is_plausible_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _resolve_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if _is_plausible_ip(candidate):
            return candidate
    if request.client and request.client.host:
        host = request.client.host.strip()
        if _is_plausible_ip(host):
            return host
    return "anon"


def _maybe_cleanup_rate_limit_store(now: float) -> None:
    stale_keys = []
    for k, v in list(RATE_LIMIT_STORE.items()):
        valid_ts = [t for t in v if t > now - RATE_LIMIT_WINDOW]
        if not valid_ts:
            stale_keys.append(k)
        else:
            RATE_LIMIT_STORE[k] = valid_ts
    for k in stale_keys:
        RATE_LIMIT_STORE.pop(k, None)


def _enforce_rate_limit(store_key: str, max_requests: int, now: float) -> None:
    global _rate_limit_cleanup_counter

    with RATE_LIMIT_LOCK:
        _rate_limit_cleanup_counter += 1
        if _rate_limit_cleanup_counter > 1000:
            _rate_limit_cleanup_counter = 0
            _maybe_cleanup_rate_limit_store(now)

        history = RATE_LIMIT_STORE.get(store_key, [])
        history = [t for t in history if t > now - RATE_LIMIT_WINDOW]

        if len(history) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
            )

        history.append(now)
        RATE_LIMIT_STORE[store_key] = history


def rate_limit_by_ip(request: Request) -> None:
    """Public-route rate limiter keyed by (client_ip, route_group)."""
    now = time.time()
    route_group = _get_route_group(request.url.path)
    max_requests = _public_rate_limit_for(route_group)
    client_ip = _resolve_client_ip(request)
    store_key = f"ip:{client_ip}:{route_group}"
    _enforce_rate_limit(store_key, max_requests, now)


def _matches_admin_api_key(provided_key: str, admin_key: str) -> bool:
    normalized_key = provided_key.strip()
    if len(normalized_key) == len(admin_key):
        return secrets.compare_digest(normalized_key, admin_key)

    # Run a same-length dummy comparison to avoid leaking the admin key length.
    secrets.compare_digest(admin_key, admin_key)
    return False


def verify_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
) -> APIKey:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )

    if len(api_key) > 256:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API Key.")

    # --- Master Key Check (for Stateless Deployments like Railway) ---

    admin_key = os.environ.get("ADMIN_API_KEY", "").strip()
    if admin_key and _matches_admin_api_key(api_key, admin_key):
        request.state.api_key_owner = "admin"
        return APIKey(key=api_key, owner="admin", is_active=True)

    db = SessionLocal()
    key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
    db.close()

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key.",
        )

    if not key_record.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Key is inactive")

    # --- Rate Limiting ---
    now = time.time()
    route_group, max_requests = _get_route_group_and_limit(request.url.path)
    store_key = f"{api_key}:{route_group}"
    _enforce_rate_limit(store_key, max_requests, now)

    request.state.api_key_owner = key_record.owner
    return key_record


def verify_api_key_if_required(
    request: Request,
    api_key: str = Security(api_key_header),
) -> APIKey | None:
    if api_key and len(api_key) > 256:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API Key.")

    if os.environ.get("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return verify_api_key(request, api_key)
    return None
