## 2024-03-07 - [Fix Path Traversal in File Upload Endpoint]
**Vulnerability:** The `/rag/upload` endpoint `upload_file_endpoint` in `api/main.py` directly concatenated `req.filename` into a local path using `os.path.join(temp_dir, req.filename)` without any sanitization.
**Learning:** This is a classic path traversal vulnerability where an attacker could upload files to an arbitrary location outside of the intended `temp_dir` by using sequences like `../` in `req.filename`.
**Prevention:** Always sanitize user-provided filenames before using them in file system operations. `os.path.basename` is an effective way to extract just the filename from a given path, ignoring any directory traversal sequences. Added fallback logic for when the basename resolves to empty or relative current directory constructs (`.` or `..`).

## 2025-03-03 - [Fix Information Leakage in API Endpoints]
**Vulnerability:** Multiple endpoints in `api/main.py` (`compile_fast`, `generate_skill_endpoint`, `generate_agent_endpoint`, `optimize_endpoint`) were returning raw exception details `str(e)` directly to the client via HTTP 500 errors.
**Learning:** Returning raw exception details is a major security risk (Information Exposure) as it can leak sensitive internal implementation details, such as file paths, database schemas, third-party API keys, or stack traces.
**Prevention:** Catch exceptions, log their details internally (e.g., via `print` or a logger for debugging), and raise an `HTTPException` with a generic `detail` message (like "An internal error occurred.") rather than returning `str(e)` directly to the user.

## 2026-03-11 - [Fix Information Leakage in Compile Endpoint via Client-Side Secrets]
**Vulnerability:** A proposal to secure the backend `/compile` endpoint involved exposing the backend API key directly to the public browser bundle via a `NEXT_PUBLIC_API_KEY` environment variable in the Next.js frontend, defeating the purpose of the authentication.
**Learning:** Exposing backend API keys or secrets directly in frontend code (even if suggested or seemingly convenient) creates a critical vulnerability where any client can extract the secret and bypass rate limiting or authentication.
**Prevention:** When a frontend SPA or static export needs to securely authenticate with a backend API, use a Backend-For-Frontend (BFF) pattern. Create a server-side proxy route (e.g., a Next.js API route) that securely injects the server-side environment variable (`process.env.API_KEY`) into the request headers before forwarding it to the backend.
