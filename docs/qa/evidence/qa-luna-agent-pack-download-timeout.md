# Agent Pack backend download evidence

Date: 2026-09-12

This was one harmless representative Agent Pack request. The UI had already rendered a seven-file Claude Project Pack for the disposable QA brief. No generated code was executed.

Request:

```json
{
  "project_type": "Local FastAPI service",
  "stack": "Python + FastAPI",
  "goal": "Review repository setup docs and flag missing prerequisites before a human commits the pack.",
  "pack_type": "project-pack",
  "risk_mode": "balanced"
}
```

```text
POST http://127.0.0.1:8080/agent-packs/claude/download
curl --max-time 25
Result: curl (28) Operation timed out after 25009 milliseconds with 0 bytes received
```

The route implementation rebuilds the manifest before returning the ZIP (`api/routes/agent_packs.py:39-54`). This check was not retried to avoid another provider call. The user-facing UI download uses the already-rendered manifest client-side and produced `/Users/mehmetozel/Downloads/local-fastapi-service-project-pack-claude.zip`; its archive was inspected and contained the seven preview files. Therefore the backend endpoint timeout is a confirmed API-path observation, while the UI download path passed.
