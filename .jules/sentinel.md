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
