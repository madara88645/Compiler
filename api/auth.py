import logging
import time
import secrets
from pathlib import Path
from typing import Dict
import os

from fastapi import HTTPException, Security, status
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
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10


def verify_api_key(
    api_key: str = Security(api_key_header),
) -> APIKey:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )

    # --- Master Key Check (for Stateless Deployments like Railway) ---
    import os

    admin_key = os.environ.get("ADMIN_API_KEY", "").strip()
    if admin_key:
        if secrets.compare_digest(api_key.strip(), admin_key):
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
    history = RATE_LIMIT_STORE.get(api_key, [])
    # Filter out timestamps older than window
    history = [t for t in history if t > now - RATE_LIMIT_WINDOW]

    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    history.append(now)
    RATE_LIMIT_STORE[api_key] = history

    return key_record


def verify_api_key_if_required(
    api_key: str = Security(api_key_header),
) -> APIKey | None:
    if os.environ.get("PROMPTC_REQUIRE_API_KEY_FOR_ALL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return verify_api_key(api_key)
    return None
