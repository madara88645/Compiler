## 2024-05-24 - Fix XSS vulnerability in DiffViewer

**Vulnerability:** Found a Cross-Site Scripting (XSS) vulnerability in `web/app/components/DiffViewer.tsx`. The component used `dangerouslySetInnerHTML` to render an HTML string generated from diff text replacements without any HTML sanitization.
**Learning:** React's `dangerouslySetInnerHTML` is susceptible to XSS if the input text contains unescaped malicious HTML payloads. It is critical to sanitize any dynamically generated HTML before rendering it in the browser. Furthermore, when using a sanitizer like `DOMPurify` within a Next.js (SSR) application, special care must be taken to only run the sanitization and render the HTML on the client side (after the initial mount) to prevent React hydration mismatch errors or server-side crashes due to the missing `window` object.
**Prevention:** Always use a robust HTML sanitization library (like `DOMPurify`) when dealing with `dangerouslySetInnerHTML`. In Next.js applications, use a combination of `useState` and `useEffect` (e.g., an `isClient` flag) to defer the rendering of sanitized HTML until the component has mounted on the client.

## 2025-03-03 - [Fix Information Leakage in API Endpoints]
**Vulnerability:** Multiple endpoints in `api/main.py` (`compile_fast`, `generate_skill_endpoint`, `generate_agent_endpoint`, `optimize_endpoint`) were returning raw exception details `str(e)` directly to the client via HTTP 500 errors.
**Learning:** Returning raw exception details is a major security risk (Information Exposure) as it can leak sensitive internal implementation details, such as file paths, database schemas, third-party API keys, or stack traces.
**Prevention:** Catch exceptions, log their details internally (e.g., via `print` or a logger for debugging), and raise an `HTTPException` with a generic `detail` message (like "An internal error occurred.") rather than returning `str(e)` directly to the user.
## 2024-05-24 - Command Injection via Unsafe Subprocess Execution with Environment Variables
**Vulnerability:** The application used `subprocess.run([editor, temp_path])` where `editor` could be derived from `os.environ.get("EDITOR")`. A malicious string with arguments or embedded shell commands (if shell=True was added later) could cause unexpected execution.
**Learning:** Directly passing unstructured environment variables like `EDITOR` into `subprocess.run()` without splitting them can lead to command execution bugs (e.g., `nano -w` failing as "nano -w" file not found) or security vulnerabilities if the path allows arbitrary strings.
**Prevention:** Always use `shlex.split()` to safely tokenize shell-like strings containing arguments before passing them as the first argument to `subprocess.run()`.
## 2025-05-30 - Fix Insecure Absolute Fallback Paths for Local Databases
**Vulnerability:** The application used a hardcoded absolute fallback path (`C:\`) to construct the default database directory when the `USERPROFILE` environment variable was missing on Windows systems (e.g., in `app/history/manager.py` and `app/rag/simple_index.py`).
**Learning:** Hardcoding root directories like `C:\` as fallbacks for storing sensitive user databases exposes data cross-user, and often leads to permission errors or path traversal vulnerabilities in environments with restricted permissions.
**Prevention:** Always use safe, dynamic cross-platform resolution methods like `os.path.expanduser('~')` as fallbacks to ensure user-specific data is safely scoped to their personal home directory.
## 2025-03-27 - Wildcard Injection in SQLite Fallback Queries
**Vulnerability:** The RAG index fallback search used string interpolation to wrap the user's query with wildcards for a SQL `LIKE` query (`LIKE f"%{query}%"`), allowing users to inject literal `%` and `_` characters to bypass search filters.
**Learning:** Using parameterized queries (e.g., `LIKE ?` with `("%" + query + "%",)`) prevents SQL injection, but does not prevent wildcard injection if the parameter itself contains unescaped wildcards.
**Prevention:** When wrapping user input in wildcards for `LIKE` queries, explicitly escape `\`, `%`, and `_` in the input string, and append the `ESCAPE '\'` clause to the SQL statement.
## 2025-03-09 - Prevent path disclosure in PathSecurityError handling
**Vulnerability:** Path disclosure vulnerability
**Learning:** `PathSecurityError` exception message explicitly included the absolute paths to the allowed directories on the server. Because the API route `rag_ingest` caught this exception and returned `str(exc)` in the 400 error `detail`, this exposed internal server paths to the client.
**Prevention:** Do not expose raw internal exception strings to the API layer, especially for filesystem or database errors. Always sanitize error messages to be generic.
## 2025-05-31 - Add Content-Security-Policy header to FastAPI without breaking Swagger UI
**Vulnerability:** The application's `api/main.py` lacked a `Content-Security-Policy` header, leaving it more vulnerable to XSS and other content injection attacks.
**Learning:** Adding a generic strict CSP (like `default-src 'none'`) or missing required sources breaks the built-in FastAPI Swagger UI and ReDoc pages, as they dynamically load assets (scripts, styles, images) from `cdn.jsdelivr.net` and `fastapi.tiangolo.com`. This is a surprising architectural constraint where tightening security headers must explicitly accommodate the documentation framework's external dependencies.
**Prevention:** When adding CSP headers to FastAPI, ensure `script-src` and `style-src` whitelist `'unsafe-inline'` and `https://cdn.jsdelivr.net`, and that `img-src` allows `data:` URIs and `https://fastapi.tiangolo.com`, to prevent breaking the `/docs` endpoints while still enforcing a policy.
## 2025-06-05 - Restrict Overly Permissive CORS Headers

**Vulnerability:** The FastAPI application used `allow_headers=["*"]` in its `CORSMiddleware` configuration. This is an overly permissive setting that could potentially allow malicious cross-origin requests to send unexpected or forged headers to the backend, increasing the attack surface.
**Learning:** While allowing all origins (`*`) is a known risk, allowing all headers (`*`) is also a security concern. It violates the principle of least privilege.
**Prevention:** When configuring CORS, always explicitly list the headers required by the application (e.g., `["Content-Type", "Authorization", "x-api-key", "Accept", "Origin", "X-Requested-With"]`) instead of using wildcards.
## 2024-05-24 - Missing Authentication on Cost-Incurring Endpoint
**Vulnerability:** The `/benchmark/run` API endpoint in `app/routers/benchmark.py`, which makes multiple LLM API calls, was completely unauthenticated.
**Learning:** Endpoints added later in the lifecycle (like benchmark routers) can sometimes be missed when applying global or required authentication patterns used in core routers (like `rag` or `compile`), leading to unauthorized resource exhaustion.
**Prevention:** Always verify that newly added routers or endpoints that trigger cost-incurring actions (like LLM calls) explicitly include standard authentication dependencies (e.g., `Depends(verify_api_key)` or `Depends(verify_api_key_if_required)`) in their signature, matching the pattern used in the rest of the application.
