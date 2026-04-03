# AI Agent Development Guidelines for myCompiler

Welcome. You are operating as an AI developer within the `myCompiler` project. This document outlines the mandatory architectural and security constraints you must adhere to when making any modifications to the codebase. Strict compliance is non-negotiable.

## 1. Architectural Overview

Understanding the system's architecture is critical for implementing safe and coherent changes.

*   **Frontend/API Layer (`api/main.py`)**: Uses FastAPI to expose endpoints for prompt compilation, RAG operations, and agent generation. Authentication relies on API keys managed via a local SQLite database.
*   **Core Logic (`app/compiler.py`)**: Implements a Chain of Responsibility pattern. Input text is processed through sequential Handlers (e.g., Safety, Risk, Logic) to produce an Intermediate Representation (IR).
*   **Intelligence Layer (`app/llm_engine`)**: Interfaces with external LLMs (e.g., Groq, OpenAI). The `HybridCompiler` orchestrates local heuristics alongside LLM capabilities.
*   **Data/RAG Layer (`app/rag/simple_index.py`)**: Provides lightweight Retrieval-Augmented Generation using SQLite FTS5 and basic embeddings. It handles local file indexing and context retrieval.

## 2. Security Imperatives

The following security hotspots have been identified. You must proactively defend against these vulnerabilities in all your implementations.

### 2.1 Arbitrary File Access & Path Traversal (CRITICAL)

The system interacts with local file paths, notably in the `/rag/ingest` endpoint which reads files via `Path.read_text()`.

*   **Mandatory Path Validation**: Never accept raw, unvalidated file paths from user input.
*   **Strict Anchoring**: All dynamic paths must be strictly resolved and anchored to a pre-defined, secure base directory (allowlist).
*   **Traversal Prevention**: Explicitly reject paths containing `..` or attempting to navigate outside the authorized boundaries. Utilize `os.path.abspath` or `pathlib.Path.resolve()` and verify the resulting path starts with the allowed base directory.

### 2.2 Prompt Injection & System Leakage

Every endpoint that routes user input to an LLM (e.g., `/compile`, `/agent-generator/generate`) is a potential attack vector for prompt injection.

*   **Beyond Redaction**: While `scan_text` redacts secrets, it does not stop logic-based injection or system prompt extraction.
*   **Input Sanitization**: Treat all user-provided text as adversarial. Enforce strict type validation, length limits, and structural constraints before passing data to the LLM.
*   **Context Isolation**: Clearly delimit user input from system instructions when constructing LLM prompts (e.g., using XML tags or distinct message roles) to prevent the LLM from misinterpreting user data as commands.

### 2.3 Database Security

SQLite is utilized for both authentication (`users.db`) and the RAG index.

*   **Parameterized Queries**: Always use parameterized queries for database operations to prevent SQL injection. Never concatenate user input directly into SQL strings.
*   **File Permissions**: Since the database relies on local files, ensure any code modifying or creating these files sets restrictive, least-privilege file permissions (e.g., read/write only for the application user).

### 2.4 Dynamic Code Generation & RCE Risks

The `Agent` and `Skill` generators produce markdown that may contain pseudo-code, scripts, or configurations.

*   **Execution Isolation**: Assume generated code is untrusted. If this output is ever executed via adapters or piped into an environment, it presents a Remote Code Execution (RCE) risk.
*   **Sandboxing**: Any mechanism that evaluates or runs generated code MUST occur within a strictly isolated, ephemeral sandbox with no access to the host network or sensitive file systems.
*   **Output Validation**: Implement heuristic checks on generated code to flag or neutralize obviously malicious patterns before it is presented or processed.

### 2.5 Secrets Management

The system relies on sensitive configuration values, such as `ADMIN_API_KEY`, passed via environment variables.

*   **Zero Exposure**: Never hardcode secrets in the codebase.
*   **No Logging**: Strictly prohibit the logging, printing, or returning of environment variables, API keys, or database credentials in API responses, error messages, or application logs.
*   **Memory Safety**: Ensure secrets are cleared from memory when no longer needed, and never include them in crash dumps or debug outputs.

## 3. Implementation Rules for Modifying Endpoints

When modifying existing or creating new FastAPI endpoints, you must adhere to the following workflow:

1.  **Validate Input**: Implement rigorous Pydantic models for all incoming request bodies and parameters.
2.  **Authenticate & Authorize**: Ensure appropriate dependency injection (e.g., API key verification) is applied to protect the endpoint.
3.  **Sanitize & Anchor**: If the endpoint interacts with the filesystem or database, apply the path anchoring and parameterization rules defined above.
4.  **Handle Errors Gracefully**: Catch exceptions and return generic, safe HTTP error responses. Do not leak stack traces or internal system state to the client.
5.  **Review for Injections**: If the endpoint forwards data to the LLM, verify that context isolation and sanitization mechanisms are in place.

By strictly following these guidelines, you ensure the integrity, security, and robustness of the `myCompiler` architecture.

## Cursor Cloud specific instructions

### Services overview

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| **FastAPI backend** | `python3 -m uvicorn api.main:app --reload --port 8080` | 8080 | Core API; all other surfaces depend on it |
| **Next.js frontend** | `cd web && npm run dev` | 3000 | Primary UI |

The backend works in **offline heuristics mode** without LLM API keys. To enable LLM-powered compilation, set `GROQ_API_KEY` or `OPENAI_API_KEY` in `.env`.

### Lint / Test / Build

Standard commands are documented in `README.md`. Quick reference:

- **Python lint**: `ruff check .` (from repo root)
- **Python tests**: `pytest -q` (734+ tests, all offline-safe, ~23s)
- **Frontend lint**: `cd web && npx eslint`
- **Frontend contract tests**: `cd web && npm run test:contracts` (requires backend running)

### Gotchas

- `python` is not on PATH in the Cloud VM; always use `python3`.
- pip installs scripts to `~/.local/bin`; ensure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`).
- The `.env` file must exist for the backend to start (copy from `.env.example` if missing).
- SQLite databases (RAG index, user auth) are created automatically at runtime — no external DB needed.
- The backend's `--reload` flag watches the entire `/workspace` directory; avoid creating large temp files in the repo root.
