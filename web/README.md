# Prompt Compiler Web

Next.js frontend for `myCompiler`.

## Package Manager

Use `npm` only. This app is locked with `package-lock.json`.

```bash
npm ci
```

## Scripts

```bash
npm run dev
npm run lint
npm run build
npm run test:contracts
```

`test:contracts` runs the lightweight Vitest contract tests for the shared API layer and Next proxy routes.

## Frontend Architecture

- `app/page.tsx` is now mostly presentational.
- `app/hooks/useCompiler.ts` owns compile request flow and security-review resume logic.
- `app/hooks/useContextManager.ts` owns RAG upload/search/stats orchestration.
- `lib/api/types.ts` defines shared compile and RAG types.
- `lib/api/promptc.ts` normalizes backend payloads so components do not depend on ad-hoc field names.
- `app/**/route.ts` mirrors backend endpoints through same-origin Next route proxies so the browser never needs a backend secret.

## Backend Assumptions

- Browser calls stay same-origin and hit the Next proxy layer first. Server-side proxy handlers forward to `NEXT_PUBLIC_API_URL` (or `http://127.0.0.1:8080` locally).
- Public web flows should never ask visitors for a Prompt Compiler API key or rely on proxy-only secret setup in the browser.
- If a cloud feature needs credentials, that configuration belongs on the backend via provider keys such as `OPENAI_API_KEY` or `GROQ_API_KEY`.
- `/rag/search` returns canonical items shaped like `{ path, snippet, score }`.
- `/rag/upload` returns canonical ingest metadata and may also include compatibility fields.
- Public app routes should not return `403` just because a Prompt Compiler-specific API key is missing.
