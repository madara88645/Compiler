# Typewriter Animation Parity — Design

- **Date:** 2026-07-03
- **Status:** Approved (design), pending spec review → implementation plan
- **Scope:** Frontend only (`web/`)

## Goal

The "or try an example" affordance types its example prompt in character-by-character
(typewriter effect) **only** on the main compile surface (`web/app/page.tsx`). Every other
generator surface fills the field **instantly**. Bring the animation to the sibling surfaces
by extracting the existing logic into one reusable hook and wiring it in.

## Current State (confirmed by code map)

- Reference implementation lives in `web/app/page.tsx` (lines ~165–196): a `typewriterRef`
  (`useRef<number|null>`), a `stopTypewriter()` (clearInterval + null the ref), a
  `prefers-reduced-motion` bailout (set full text instantly), `stepChars = Math.max(1, Math.ceil(text.length / 40))`,
  a 16ms `setInterval` advancing `setPrompt(text.slice(0, i))`, unmount cleanup via
  `useEffect(() => stopTypewriter, [])`, and defensive cancellation on textarea `onChange`
  (line ~299) and Clear (line ~312). No framer-motion; plain `setInterval` + React state.
- Surfaces **missing** the animation (fill instantly today):
  | Surface | File | State setter | Focus target |
  |---|---|---|---|
  | agent-generator | `web/app/agent-generator/page.tsx` | `setDescription` | id `agent-description` |
  | skills-generator | `web/app/skills-generator/page.tsx` | `setDescription` | id `skill-description` |
  | benchmark | `web/app/benchmark/page.tsx` | `setPrompt` | id `benchmark-prompt` |
  | optimizer | `web/app/optimizer/page.tsx` | `setInput` | none today (add one) |
  | agent-packs | `web/app/agent-packs/page.tsx` | `handleFieldChange('goal', …)` | id `agent-pack-goal` |
  | offline | `web/app/offline/page.tsx` | `setPrompt` (2 buttons) | id `offline-prompt` |
- **Out of scope:** `web/app/pr-safety/page.tsx` — its `loadExample()` fills four fields
  from an `EXAMPLE` constant (title/description/changedFiles/commitsBehind) and uses
  different button copy; it does not fit the single-field typewriter pattern.

## Design

### New hook — `web/app/hooks/useTypewriterFill.ts`

Encapsulates the reference logic so there is exactly one implementation.

```ts
// Conceptual signature — final types decided in the plan.
function useTypewriterFill(
  setter: (value: string) => void,
  focusTarget?: { id?: string; selector?: string },
): { fillExample: (text: string) => void; stop: () => void };
```

Behavior (identical to today's main surface):
- Cancels any in-flight run, then focuses the target (`getElementById(id)` or `querySelector(selector)`).
- If `prefers-reduced-motion: reduce` → set full text instantly and return.
- Otherwise clear the field, then `setInterval(16ms)` advancing by `stepChars = max(1, ceil(len/40))`
  so total runtime is ~0.65s and length-independent; stop when complete.
- Interval id held in a ref; cleared on unmount.

### Wiring per surface

- Replace each "or try an example" `onClick` instant `setX(...)` with `fillExample(...)`.
- Wire `stop()` into each surface's textarea `onChange` and Clear handler so manual typing
  cancels an in-flight animation (mirroring main).
- **Refactor `web/app/page.tsx` to consume the hook too**, removing the duplicated inline
  logic (improve the code we're touching; single source of truth).
- Special cases:
  - **agent-packs:** setter is `(v) => handleFieldChange('goal', v)`; each tick feeds the sliced string.
  - **optimizer:** add a focus target (give the textarea an `id`, e.g. `optimizer-input`) for parity.
  - **offline:** both example buttons use the same hook instance (setter `setPrompt`, id `offline-prompt`).

## Testing

- Per surface: a click test asserting the field ends up with the full example text.
- `prefers-reduced-motion` path (instant fill) — mock `matchMedia` to `matches: true`.
- Timer path — `vi.useFakeTimers()` + advance to assert intermediate/typed state, or assert
  final state after running all timers.
- Keep existing tests green (main surface behavior unchanged after refactor).

## Non-Goals

- No new animation library (no framer-motion).
- No change to `pr-safety`.
- No change to example prompt copy.

## Files

- **New:** `web/app/hooks/useTypewriterFill.ts` (+ test).
- **Modified:** `web/app/page.tsx` (refactor to hook), and the 6 sibling surfaces listed above
  (+ their tests).
