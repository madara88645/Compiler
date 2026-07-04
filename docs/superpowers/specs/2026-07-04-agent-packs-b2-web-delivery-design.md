# Agent Packs B2 — Web Delivery Polish (Design)

- **Date:** 2026-07-04
- **Status:** Approved (design), pending spec review
- **Branch:** `feat/agent-packs-web-b2` (off `main`, independent of B1 / PR #933)
- **Surface:** `web/app/agent-packs/**` only — backend, API, and MCP untouched.

## Problem

The Agent Packs web surface generates repo-ready assets but its delivery UX is weak in
five concrete ways:

1. **Download re-generates on the server.** Clicking "Download Pack" POSTs the request a
   second time to `/agent-packs/claude/download`, re-running generation. Generation is
   deterministic today (heuristic, not LLM), so this is not a correctness bug, but it is a
   wasted round-trip, hits a separate rate limit, and gives no hard guarantee that the
   bytes downloaded equal the bytes previewed.
2. **Static install checklist.** `InstallChecklist.tsx` renders plain bullets. Users can't
   track which install/review steps they've completed.
3. **No file tree, no per-file download.** Preview navigation is a flat set of
   group-by-kind tabs plus a `<select>`. There is no view of files in their real repo
   paths, and no way to grab a single file.
4. **Dead provider card.** `page.tsx` renders a `<button aria-label="Claude provider
   card">` with no `onClick` — it does nothing. There is only one provider (Claude).
5. **Over-hedged copy.** "Beta", "Beta Preview", "Experimental Feature", "beta-stage",
   "beta output", "beta preview" appear repeatedly, reading as fear-marketing rather than
   an honest single caveat.

## Goals / Non-goals

**Goals:** fix all five above on the existing web surface, keep the product honest (one
calm caveat, not zero), and keep the change independently mergeable.

**Non-goals:** No backend/API/MCP changes. No B3 work (dead IR fields, `CLAUDE.md`
smart-merge, CLI/GitHub vehicles). No persistence of checklist state across reloads. No
new provider. No redesign of the generation form (project type / stack / goal / pack type
/ risk mode stay as-is). No full ARIA `role="tree"` keyboard navigation (see §3).

## Approved decisions

- **Whole-pack download is built client-side from the in-state manifest**, using the
  `fflate` library. Mehmet explicitly approved adding this one dependency this session
  (dependencies are normally a hard boundary). `fflate` is ~8KB, zero-dependency,
  tree-shakeable, actively maintained; its synchronous `zipSync` + `strToU8` (and
  `unzipSync` for tests) fit a small-text-file zip. The PR description will call out the
  added dependency explicitly.
- **Branch off `main`** as an independent PR. B2 does not need B1's backend.
- **Checklist state is in-session only** (resets on generate and on close). No localStorage.

## Design

All new logic goes in small, pure, independently testable units. `page.tsx` shrinks as
tab/select navigation is replaced by the tree.

### 1. Client-side pack zip — `lib/packZip.ts`

- `buildPackZip(files: AgentPackFile[]): Blob` — maps each file to
  `{ [file.path]: strToU8(file.content) }` and returns `new Blob([zipSync(entries)], {
  type: "application/zip" })`. `buildPackZip([])` returns a valid **empty** zip Blob
  (`zipSync({})` is well-defined); the UI guard below prevents ever downloading one.
- `handleDownload` in `page.tsx`:
  - No longer calls `apiFetch("/agent-packs/claude/download", …)`. It is fully client-side.
  - **Guard:** early-returns if `!manifest || manifest.files.length === 0` (defensive;
    the Download Pack button only renders when a manifest exists, and real manifests always
    have ≥1 file, so this is unreachable in normal UI flow — no user-facing error, just a
    no-op).
  - Builds the Blob via `buildPackZip(manifest.files)`, then reuses the existing
    anchor-download flow (append anchor → click → remove → `revokeObjectURL` on next tick).
  - Filename = `${manifest.download_name || "agent-pack"}.zip`.
    (`AgentPackManifest.download_name` already exists in `types.ts` — no type change.)
  - Wrapped in try/catch; on failure sets the visible error and clears the busy state.
  - On success sets `downloaded = true` (drives the "Downloaded" checklist state). It does
    **not** reset checked checklist items.
- Remove now-dead code from `page.tsx`: the `apiFetch` import and the `getDownloadFilename`
  helper (both only served the server download; after this change `page.tsx` uses only
  `apiJson`).
- **The server `/agent-packs/claude/download` endpoint and the Next.js proxy route
  (`web/app/agent-packs/claude/download/route.ts`) are kept.** They remain valid and
  tested (`proxy-routes.test.ts` imports the route handler directly and is unaffected) and
  may serve non-UI clients (direct API, future CLI). The UI simply stops depending on them.

### 2. Interactive install checklist

- `installChecklist.ts` (the generator) is **unchanged** — it still returns the four
  sections (`generatedFiles`, `reviewFirst`, `validationSteps`, `nextAction`) as
  `{ id, title, items: string[] }`, and its section titles ("Review before use",
  "Suggested validation", etc.) are unchanged. Its unit tests stay green. It intentionally
  keeps emitting a `generatedFiles` section that the component no longer renders; a future
  cleanup that removes it must also update `installChecklist.test.ts:44-53`.
- `InstallChecklist.tsx` becomes interactive:
  - **Rendered sections and checkbox rule (explicit):**
    - `generatedFiles` — **not rendered** (the file tree in §3 lists the files; rendering
      them again would duplicate).
    - `reviewFirst` — rendered; each item is a **checkbox**.
    - `validationSteps` — rendered; each item is a **checkbox**.
    - `nextAction` — rendered as **plain guidance text** (not a checkbox): it is a single
      advisory sentence and its copy changes with `downloaded`, which would make checkbox
      ids unstable.
  - **Checkbox items = `reviewFirst.items ∪ validationSteps.items`.** Each item's id is
    `${section.id}-${index}`. These ids are stable for a given generated manifest:
    neither `reviewFirst` nor `validationSteps` depends on `downloaded`, and the file set
    is fixed until a regenerate (which resets state). Only `nextAction` is
    `downloaded`-dependent, and it is excluded from checkboxes.
  - **Progress:** `total` = number of rendered checkbox items (reviewFirst + validationSteps
    only). Show `${checked}/${total} done` with a thin progress bar; at
    `checked === total` show a subtle "All steps complete" state. The existing "Downloaded"
    badge stays.
  - **State:** checked ids live in `page.tsx` as `Set<string>`, passed down with a toggle
    handler. Reset (cleared to empty) on **generate** and on **close** — the same resets
    that already clear `manifest`, `downloaded`, `activeKind`, etc. **Not** reset on
    download.
  - **Accessibility contract (testable):** each checkbox is a real `<input
    type="checkbox">` with an associated `<label>` whose text is the item string, so
    `getByRole("checkbox", { name: <item text> })` resolves. The section keeps its
    `aria-labelledby` heading (`getByRole("group")` present).

### 3. File tree + per-file download

- `lib/fileTree.ts` — pure: `buildFileTree(files: AgentPackFile[]): TreeNode[]` splits each
  `file.path` on `/` into nested folder/file nodes. Folders sort before files;
  alphabetical within a level. Each file node carries a reference to its `AgentPackFile`.
- `components/FileTree.tsx` — renders collapsible folders and selectable file rows.
  - **a11y contract (testable, no full ARIA tree):** each **file row** is a `<button>` with
    accessible name = the file's **basename** (e.g. `CLAUDE.md`, `pr-reviewer.md`); each
    **folder row** is a `<button aria-expanded>` with accessible name = the folder
    **segment** (e.g. `.claude`, `agents`); each file row also has a separate download
    `<button>` with accessible name `Download {basename}`. Nested `<ul>`/`<li>`. Full ARIA
    `role="tree"` arrow-key navigation is out of scope for B2 (documented non-goal).
  - Selecting a file row sets `selectedPath`; the preview `<pre>` pane renders that file.
  - Each file row's download button downloads **that single file**:
    `new Blob([file.content])`, filename = **basename** of `file.path` (paths flatten —
    `.claude/agents/pr-reviewer.md` downloads as `pr-reviewer.md`), same anchor flow. No
    zip for a single file.
  - Replaces the group-by-kind tab bar (`previewGroups`, `PREVIEW_LABELS`) and the
    `<select>` file picker. Those and their derived state are removed from `page.tsx`.
- **Preview pane data flow (changes, though its markup is the same):** `currentFile` is
  recomputed independently of the removed group state as
  `manifest.files.find(f => f.path === selectedPath) ?? manifest.files[0] ?? null`. The
  `<pre>` still renders `currentFile?.content`.
- **Copy controls:** `handleCopyCurrent` is repointed to the new `currentFile` (the
  tree-selected file). `handleCopyAll`, `handleDownload` (whole zip), and Close are
  otherwise unchanged in behavior. So the header keeps Copy / Copy All / Download Pack /
  Close — Copy now copies the tree-selected file.

### 4. Remove the dead provider card

- Delete the no-op `<button aria-label="Claude provider card">` block in `page.tsx`.
- `providerRegistry.ts` stays (still supplies name, cta label, accent/glow/button
  classes used across the header and buttons). Only the redundant card UI is removed and
  the wording is trimmed (see §5).

### 5. Dial back beta / experimental hedging

- Reduce many hedges to **exactly one** honest caveat:
  - Keep a single small **"Beta"** badge in the header (`page.tsx:233-235`), text node
    exactly `Beta`. This is the only "Beta" occurrence on the page after this change.
  - Keep one concise review caveat inside the checklist intro copy ("Generated files are a
    starting point — review before committing."). The generator's section titles (e.g.
    "Review before use") are unchanged.
  - Remove: the "Experimental Feature" amber box, the "beta-stage agent assets" heading
    text (→ e.g. "Generate agent assets for your repo"), and the dead card's "Beta
    preview…" copy (the card is deleted anyway).
  - `providerRegistry.ts` exact target strings: `badge: ""` (so the header chip renders
    just `Claude`, not `Claude Beta Preview`) and
    `summary: "Generate repo-ready Claude assets from one short brief."`
- This is "dial back" (memo: *azalt*), not "erase" — one responsible caveat remains.

## File-level impact

**New:**
- `web/app/agent-packs/lib/packZip.ts`
- `web/app/agent-packs/lib/fileTree.ts`
- `web/app/agent-packs/components/FileTree.tsx`
- Tests: `lib/packZip.test.ts`, `lib/fileTree.test.ts`, `components/FileTree.test.tsx`
  (all **required**, not optional).

**Changed:**
- `web/app/agent-packs/page.tsx` — client-side download; tree replaces tabs/select;
  `currentFile` recomputed from `selectedPath`; checklist checked-state `Set`; dead card
  removed; hedging reduced; dead `apiFetch` import + `getDownloadFilename` removed.
- `web/app/agent-packs/components/InstallChecklist.tsx` — interactive checkboxes +
  progress; renders reviewFirst/validationSteps as checkboxes, nextAction as text, skips
  generatedFiles.
- `web/app/agent-packs/providerRegistry.ts` — `badge`/`summary` wording trimmed (shape
  unchanged).
- `web/package.json` — add `fflate` dependency (approved).
- `web/app/agent-packs/page.test.tsx` — see test impact below.

**Unchanged (intentionally):**
- `web/app/agent-packs/installChecklist.ts` and `installChecklist.test.ts`.
- `web/app/agent-packs/claude/download/route.ts` and `web/app/proxy-routes.test.ts`.
- `web/app/agent-packs/types.ts` (existing types suffice; `download_name` already present).
- All backend, API, and MCP code.

## Testing

**New unit/component tests:**
- `packZip.test.ts` — (a) build a zip from a multi-file manifest, `unzipSync` it, assert
  every path and its exact content round-trips; (b) `buildPackZip([])` returns a valid
  (empty) zip Blob without throwing. Deterministic, no network.
- `fileTree.test.ts` — single top-level file; nested paths
  (`.claude/agents/pr-reviewer.md`); folder-before-file ordering; alphabetical sort within
  a level.
- `FileTree.test.tsx` — folder/file rows render with the a11y names from §3; clicking a
  file row selects it (content shows); clicking a file's download button downloads a
  single-file Blob with `anchor.download === "<basename>"` (e.g. `pr-reviewer.md` for a
  nested path) and does **not** build a zip.
- `InstallChecklist` component test — reviewFirst/validationSteps items render as
  `role="checkbox"` (verifying label association); ticking a checkbox increments progress;
  `nextAction` renders as text (no checkbox); the group has its `aria-labelledby` heading.

**`page.test.tsx` updates (existing tests that assume old behavior):**
- Remove the now-orphaned `apiFetch` mock plumbing: the `vi.hoisted`/`vi.mock` `apiFetch`
  entry (lines 6-9, 11-21) and the `beforeEach` `apiFetch.mockResolvedValue(new
  Response("zip-bytes"...))` (lines 30, 42-50). After B2, `page.tsx` never calls
  `apiFetch`.
- **"surfaces beta messaging"** (lines 68-74) — drop `getByText("Experimental Feature")`;
  tighten the Beta assertion to `expect(screen.getAllByText("Beta")).toHaveLength(1)` so it
  actually enforces the "exactly one caveat" decision (a `>0` assertion would not). Keep
  the `queryByText("API Key (Optional)")` null assertion.
- **"submits the selected pack type and renders grouped preview output"** (lines 76-95) —
  replace the tab-button assertions `getByRole("button", { name: "CLAUDE.md" })` and
  `{ name: "agents" }` (lines 93-94) with file-tree assertions per the §3 contract (a
  `CLAUDE.md` file-row button; an `agents` folder button). The `getByText("Review before
  use")` assertion (line 92) still passes (section title unchanged).
- **"renders pack-specific checklist guidance for project-pack output"** (lines 97-120) —
  expected to **stay green**: its assertions `/Merge \.claude\/settings\.json carefully/`
  (line 118) and `/GitHub workflow YAML permissions/` (line 119) come from the
  `validationSteps` section, which is still rendered (now as checkbox labels). Verified
  against `installChecklist.ts` (validationSteps builder). Listed here so an implementer
  confirms rather than accidentally breaks it.
- **"downloads the generated pack through the Claude download route"** (lines 122-163) —
  rewrite: after clicking Download Pack, assert **no** `apiFetch` call, that
  `URL.createObjectURL` was called once, that the created anchor's
  `download === "saas-pr-reviewer-claude.zip"` (from the fixture `download_name`), that the
  anchor was clicked, and that the "Downloaded" state appears.
- **New download fallback case** — with an `apiJson` manifest that omits `download_name`,
  assert the anchor `download === "agent-pack.zip"`.
- **"…empty…" (lines 165-211) and "…download fails…" (lines 213-240)** — the server-driven
  failure modes no longer exist. Replace with a **files:[] guard test**: render with an
  `apiJson` manifest whose `files: []`, click Download Pack, assert `URL.createObjectURL`
  was **not** called and the anchor was **not** clicked (no-op guard). Remove the obsolete
  "empty server blob" / 500-response assertions.
- **"closing the preview clears the generated pack and its labels"** (lines 269-287) —
  update the stale tab assertions (`{ name: "CLAUDE.md" }`, lines 278, 285) to the file-tree
  equivalent; additionally tick a checkbox, click Close, regenerate, and assert progress
  reads `0/${total}` with no boxes checked (covers the reset-on-close branch, distinct from
  reset-on-generate).
- Assert that clicking **Download** does **not** reset already-checked checkboxes (only
  flips "Downloaded").

**Unaffected:** `installChecklist.test.ts` (generator untouched); `proxy-routes.test.ts`
(tests the retained route handler directly, never imports `page.tsx`).

**Gate before PR:** `cd web && npm run test` and `cd web && npm run build` both green.

## Risks & mitigations

- **Added dependency (`fflate`).** Normally a hard boundary; explicitly approved this
  session. Mitigate by pinning it and calling it out in the PR body.
- **Test churn in `page.test.tsx`.** Several tests assert on the old tabs/server-download.
  Rewrites are scoped and enumerated above; the pure generator's tests are deliberately
  untouched to limit blast radius.
- **Checkbox id stability.** Guaranteed by excluding the only `downloaded`-dependent
  section (`nextAction`) from checkboxes and resetting the checked `Set` on every
  regenerate/close.

## Out of scope / follow-ups

- Removing the now-UI-unused `/download` endpoint + Next.js proxy route (only if confirmed
  dead). **Note:** that follow-up must also delete the three parametrized download cases in
  `proxy-routes.test.ts` (approx. lines 125-130, 205-208, 369-373), or they will fail.
- B3: render dead IR fields (hooks → settings, `mcp_servers` → `.mcp.json`), `CLAUDE.md`
  smart-merge, CLI + GitHub-PR vehicles.
- Persisting checklist progress across reloads.
- Full ARIA `role="tree"` keyboard navigation for the file tree.
