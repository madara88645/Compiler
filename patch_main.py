import re

with open("api/main.py", "r") as f:
    content = f.read()

search_pattern = r"""    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "duration_ms": duration_ms,
                "api_key_owner": getattr(request.state, "api_key_owner", None),
            },
        )
        raise"""

replace_pattern = r"""    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "duration_ms": duration_ms,
                "api_key_owner": getattr(request.state, "api_key_owner", None),
            },
        )
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            raise
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})"""

if search_pattern in content:
    content = content.replace(search_pattern, replace_pattern)
    with open("api/main.py", "w") as f:
        f.write(content)
