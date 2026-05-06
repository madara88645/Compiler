from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from fastapi import Request

from app.emitters import _is_trivial_input, emit_expanded_prompt_v2


logger = logging.getLogger("promptc.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(levelname)s:%(name)s:%(message)s method=%(method)s path=%(path)s "
            "status_code=%(status_code)s duration_ms=%(duration_ms)s client_ip=%(client_ip)s "
            "api_key_owner=%(api_key_owner)s user_agent=%(user_agent)s",
            defaults={
                "method": "-",
                "path": "-",
                "status_code": "-",
                "duration_ms": "-",
                "client_ip": "-",
                "api_key_owner": "-",
                "user_agent": "-",
            },
        )
    )
    logger.addHandler(handler)
logger.propagate = False

_META_LEAK_PATTERNS = [
    "output only valid json",
    "output only json",
    "sadece gecerli json",
    "sadece json",
    "only valid json",
    "json only",
    "return only json",
]


def is_meta_leaked(text: str) -> bool:
    lower = text.lower().strip()
    if len(lower) < 120:
        # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
        for pattern in _META_LEAK_PATTERNS:
            if pattern in lower:
                return True
    return False


def resolve_mode(req_mode: Optional[str], request: Request) -> str:
    if req_mode:
        mode = req_mode.strip().lower()
        if mode in {"conservative", "default"}:
            return mode

    header_val = request.headers.get("X-Prompt-Mode") or request.headers.get("x-prompt-mode")
    if header_val:
        mode = header_val.strip().lower()
        if mode in {"conservative", "default"}:
            return mode

    return (os.environ.get("PROMPT_COMPILER_MODE") or "conservative").strip().lower()


def forced_minimal_expanded_prompt(text: str, ir2, diagnostics: bool = False) -> str | None:
    if ir2 is None:
        return None
    complexity = (ir2.metadata or {}).get("complexity") or ""
    if _is_trivial_input(text, ir2.domain, complexity):
        return emit_expanded_prompt_v2(ir2, diagnostics=diagnostics)
    return None
