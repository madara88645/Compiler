import logging
import time
import secrets
from pathlib import Path
from threading import Lock
from typing import Dict
import os

from fastapi import HTTPException, Security, status, Request
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import create_engine, Column, String, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Database ---
import os as _os

logger = logging.getLogger("promptc.auth")


def _ensure_private_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    try:
        _os.chmod(path, 0o600)
    except OSError:
        pass


_db_dir = Path(_os.environ.get("DB_DIR", ".")).expanduser().resolve()
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


def _get_route_group_and_limit(path: str) -> tuple[str, int]:
    heavy_routes = ["/compile", "/optimize", "/run", "/agent-generator", "/skills-generator"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    for r in heavy_routes:
        if path.startswith(r):
            return "heavy", HEAVY_RATE_LIMIT_MAX_REQUESTS
    return "default", RATE_LIMIT_MAX_REQUESTS


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

    with RATE_LIMIT_LOCK:
        # Periodically clean up stale rate limit entries to prevent memory leaks
        if getattr(verify_api_key, "_cleanup_counter", 0) > 1000:
            verify_api_key._cleanup_counter = 0
            stale_keys = []
            for k, v in list(RATE_LIMIT_STORE.items()):
                valid_ts = [t for t in v if t > now - RATE_LIMIT_WINDOW]
                if not valid_ts:
                    stale_keys.append(k)
                else:
                    RATE_LIMIT_STORE[k] = valid_ts
            for k in stale_keys:
                RATE_LIMIT_STORE.pop(k, None)
        else:
            verify_api_key._cleanup_counter = getattr(verify_api_key, "_cleanup_counter", 0) + 1

        history = RATE_LIMIT_STORE.get(store_key, [])
        # Filter out timestamps older than window
        history = [t for t in history if t > now - RATE_LIMIT_WINDOW]

        if len(history) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
            )

        history.append(now)
        RATE_LIMIT_STORE[store_key] = history

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
