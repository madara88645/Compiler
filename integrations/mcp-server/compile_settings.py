"""Shared compile API URL, headers, and body for MCP and documentation."""

from __future__ import annotations

import os
from typing import Any


def resolve_compile_post_url() -> str:
    """
    Full URL for POST /compile.

    PROMPTC_API_URL: full URL including path (legacy; e.g. http://localhost:8000/compile).
    PROMPTC_BACKEND_URL: origin only; /compile is appended.
    """
    explicit = os.environ.get("PROMPTC_API_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    backend = os.environ.get("PROMPTC_BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
    return f"{backend}/compile"


def resolve_prompt_mode() -> str:
    """Matches extension default when conservative toggle is on (unset storage)."""
    mode = os.environ.get("PROMPTC_PROMPT_MODE", "conservative").strip().lower()
    return mode if mode in ("conservative", "default") else "conservative"


def resolve_api_key() -> str | None:
    key = os.environ.get("PROMPTC_API_KEY", "").strip()
    return key or None


def build_compile_headers(mode: str, api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Prompt-Mode": mode,
    }
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def build_compile_body(text: str, mode: str) -> dict[str, Any]:
    return {
        "text": text,
        "diagnostics": False,
        "v2": True,
        "render_v2_prompts": True,
        "mode": mode,
    }
