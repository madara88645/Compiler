# Agentic Coding: incremental workspace release

## Decision and scope

Keep Compiler, Token Optimizer, Benchmark and PR Safety available. Replace the three separate asset navigation entries with an Agentic Coding group: Projects, Agents, Skills & Tools. Existing generator URLs and API contracts continue to work. This implements the first navigation and shared-brief slice of the September modernization research; it does not implement an agent runner or the entire research roadmap.

Projects are named browser-local briefs (type, stack, goal, rules). They can be created, edited, deleted and reused through explicit attachment in existing generator forms. A selected project in a URL is only a candidate; it does not silently modify the task or generation request. Attachment captures a visible snapshot. Switching the candidate, saving another project, or editing the brief in another tab must not change the attached snapshot. Detachment removes the snapshot from subsequent requests.

The existing Agent Packs UI remains the export destination. All four pack types, file preview, copy, ZIP and install checklist are retained. Agents and Skills remain independently usable. No backend schema, provider, authentication, or execution behavior changes are required.

## Routes

| Navigation | Destination | Existing URL retained |
|---|---|---|
| Projects | `/agentic-coding` | `/agent-packs` remains the pack tool |
| Export pack action | `/agentic-coding/projects/export?project=<id>` | `/agent-packs` |
| Agents | `/agentic-coding/agents?project=<id>` | `/agent-generator` |
| Skills & Tools | `/agentic-coding/skills?project=<id>` | `/skills-generator` |

## Verification gates

- Saved briefs survive reload; corrupt, unavailable or full storage produces actionable visible errors.
- Unsaved editor content is not silently replaced on navigation within the hub.
- A form's task is preserved when project context is attached, replaced or detached.
- Unattached requests preserve prior payload behavior; attached requests include the selected snapshot and stay within existing input limits.
- Old and new routes have correct navigation selection; legacy output tests keep passing.
- Frontend contracts, unit tests, lint and build pass. Browser smoke checks cover new/old navigation and project reuse, without claiming live LLM output quality.

## Persona review

An AGY Understudy / Gemini 3.6 Flash High simulated concept review accepted this release for project setup and reusable context preparation, conditional on the above persistence, form preservation, snapshot and export checks. It did not establish actual user adoption or time savings. A separate Luna/max review checks implementation behavior. Future possible additions are project backup/import, versioned client export adapters and CLI context collection; they are outside this slice.

## Limits

Project briefs are stored in this browser, without account sync or backup. This feature prepares context and files; it does not run agents or synchronize a repository. Generated output still needs the existing review/install process. Research references remain in the original checkout's `docs/research/2026-09-12-modernization-*.md` files.

## Completed validation (12 September 2026)

- Full frontend unit suite: 63 files, 356 tests passed.
- Frontend contracts: 4 files, 61 tests passed.
- ESLint and production Next.js build passed, including all four new routes and the retained legacy routes.
- Browser checks passed for saved-brief creation/reload, project-card navigation, explicit pack attachment/detachment, preserved task text, restored manual pack fields, dirty-draft switching guards and editor focus.
- Layout inspected at 390px and 1440px; mobile document width matched the viewport (no horizontal document overflow).
- Browser testing caught and fixed a client-navigation query timing bug: the picker now reads Next.js search parameters inside a Suspense boundary instead of capturing window.location during initial rendering.
- Luna/max simulated persona review found the integrated context preparation flow useful after the pack metadata conflict was fixed. This is not evidence of real user adoption.
- No live provider generation or backend end-to-end run was performed. Existing generator request/output behavior is covered by mocked frontend regression tests. No deployment or remote push was performed.
