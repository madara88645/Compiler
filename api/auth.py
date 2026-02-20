import time
from typing import Dict
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import create_engine, Column, String, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Database ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./users.db"
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
        # Comparison logic (robust)
        if api_key.strip() == admin_key:
            return APIKey(key=api_key, owner="admin", is_active=True)

        # Debugging mismatch (only prints to server logs)
        print("[AUTH ERROR] Admin Key Mismatch.")
        print(f"[AUTH ERROR] Env Key (len={len(admin_key)}): {repr(admin_key)}")
        print(f"[AUTH ERROR] Recv Key (len={len(api_key)}): {repr(api_key)}")
    else:
        # Debugging missing key
        print("[AUTH DEBUG] ADMIN_API_KEY not found in environment or is empty.")

    db = SessionLocal()
    key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
    db.close()

    if not key_record:
        # DEBUG: Show what was received
        received_snippet = f"'{api_key[:5]}...'" if api_key else "None"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid API Key. Server received: {received_snippet}. Comparison failed.",
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
