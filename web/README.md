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

`test:contracts` runs the lightweight Node-based contract tests for the shared API layer.

## Frontend Architecture

- `app/page.tsx` is now mostly presentational.
- `app/hooks/useCompiler.ts` owns compile request flow and security-review resume logic.
- `app/hooks/useContextManager.ts` owns RAG upload/search/stats orchestration.
- `lib/api/types.ts` defines shared compile and RAG types.
- `lib/api/promptc.ts` normalizes backend payloads so components do not depend on ad-hoc field names.

## Backend Assumptions

- The frontend expects the API at `NEXT_PUBLIC_API_URL` or `http://127.0.0.1:8080`.
- `/rag/search` returns canonical items shaped like `{ path, snippet, score }`.
- `/rag/upload` returns canonical ingest metadata and may also include compatibility fields.
- Some routes can now return `403` when API key protection is enabled on the backend.
