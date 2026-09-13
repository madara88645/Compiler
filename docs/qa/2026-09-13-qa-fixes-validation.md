# Agentic workspace QA fixes — 2026-09-13

This follow-up closes the four actionable findings from the 2026-09-12 Luna QA report.

## Resolved

- **Quality Coach frontend 404:** added the missing Next.js `POST /validate` proxy. A manual browser run rendered a 35/100 score, four category scores, and findings instead of an error.
- **Agent Pack backend download timeout:** the download endpoint now accepts an existing manifest and creates the ZIP without regenerating agents or skills. A live request through the frontend proxy returned a two-file ZIP in 0.275 seconds.
- **Absolute RAG paths in exports:** absolute indexed paths are reduced to their basename before they enter public context suggestions. Relative paths remain unchanged and duplicate public labels are collapsed.
- **Executable export wording:** agent and skill integration targets are labeled as templates that require review before use.

## Verification

- Backend focused and regression suite: **137 passed**.
- Frontend Vitest suite: **371 passed**.
- Frontend contract suite: **64 passed**.
- Frontend lint: passed.
- Next.js production build: passed; route inventory includes `POST /validate`.
- Pre-commit hooks: passed after formatter updates.
- Live Quality Coach API through Next.js: HTTP 200 with structured category scores.
- Live Agent Pack manifest download through Next.js: HTTP 200, `application/zip`, expected Claude files present.

The historical QA report and its raw observations are preserved under `docs/qa/` and `docs/qa/evidence/`.

## Pre-merge hardening follow-up

An independent merge review found three additional risks, which were reproduced before fixing:

- Agent Pack generation ran synchronous provider work on the FastAPI event loop. All three generating routes now offload manifest construction to a worker thread, with concurrency regression coverage.
- Agent Pack frontend routes could retry a long-running POST after timeout. Those routes no longer retry automatically, and the shared proxy returns the first timeout without replaying the request.
- Client-submitted manifests lacked strict filename and size bounds. Manifests now canonicalize relative paths, reject control characters and unsafe download names, limit files and total UTF-8 content, and safely encode non-ASCII download filenames.

The optimizer provider restriction is intentional: `openrouter` and `local` are the supported values. README and contributor instructions now state that legacy provider labels return HTTP 422 and must migrate to `openrouter`.

Follow-up validation: **234 backend tests**, **372 frontend tests**, **65 frontend contracts**, lint, production build, and pre-commit passed. The frontend test process still prints known connection-refused noise from existing localhost probes, but exits successfully with all tests passing.
