# Quality Coach frontend route evidence

Date: 2026-09-12

Input used in the disposable QA browser session:

`Turn this vague bug report into a safe implementation brief for a FastAPI upload endpoint with validation, tests, and a rollback note.`

Steps:

1. Open `http://127.0.0.1:3014/`.
2. Keep the Heuristics-only engine off and compile the input above.
3. Open the `Quality Scores` tab and choose `Run quality analysis`.

Expected: the Quality Coach renders the backend validation report.

Observed: the UI renders `Quality analysis failed` and the Next.js 404 HTML error page. The browser dev log identifies the failing relative request as `/validate`. The frontend build route inventory has no `/validate` proxy route.

Independent HTTP check using the same harmless request:

```text
POST http://127.0.0.1:3014/validate
HTTP/1.1 404 Not Found
Content-Type: text/html; charset=utf-8
```

```text
POST http://127.0.0.1:8080/validate
HTTP/1.1 200 OK
Content-Type: application/json
{"score":55,"category_scores":{"clarity":70,"specificity":40,"completeness":30,"consistency":80}, ...}
```

Source/build evidence: `web/app/components/QualityCoach.tsx:63` calls `apiJson("/validate")`; `api/routes/compile.py:709` serves the backend endpoint. `npm run build` listed `/compile`, `/health`, and other proxy routes but no `/validate` route.

Classification: confirmed user-facing Quality Coach failure, P1 until the frontend proxy or direct backend routing is restored.
