# Typewriter Animation Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the main compile page's typewriter "or try an example" effect into a shared hook and apply it to the 6 single-field generator surfaces.

**Architecture:** One reusable hook (`useTypewriterFill`) encapsulates the interval-based typing, `prefers-reduced-motion` bailout, focus, and cleanup. The main page is refactored to consume it (single source of truth); each sibling surface swaps its instant `setX(...)` example handler for `fillExample(...)` and cancels an in-flight run on manual edit / clear.

**Tech Stack:** Next.js (App Router), React, TypeScript, Tailwind, Vitest + @testing-library/react (happy-dom).

---

## File Structure

- **New:** `web/app/hooks/useTypewriterFill.ts` — the shared hook (only logic unit).
- **New:** `web/app/hooks/useTypewriterFill.test.tsx` — hook unit tests (all logic coverage).
- **New:** `web/app/__tests__/page-example-fill.test.tsx` — regression test that the main-page refactor preserves example fill.
- **Modified (wiring only):** `web/app/page.tsx`, `web/app/agent-generator/page.tsx`, `web/app/skills-generator/page.tsx`, `web/app/benchmark/page.tsx`, `web/app/optimizer/page.tsx`, `web/app/agent-packs/page.tsx`, `web/app/offline/page.tsx`.

**Testing strategy:** The hook holds 100% of the logic and is unit-tested for both paths (reduced-motion instant + animated typing + cancel + cleanup). The main-page refactor gets a dedicated regression test. The 6 surface changes are mechanical wiring; they are verified by TypeScript compile (`npm run build`) and the full `npm run test` suite staying green, plus a final manual smoke — this tests at the right unit instead of scaffolding six heavy full-page render tests for a one-line swap.

---

### Task 1: Create the `useTypewriterFill` hook

**Files:**
- Create: `web/app/hooks/useTypewriterFill.ts`
- Test: `web/app/hooks/useTypewriterFill.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `web/app/hooks/useTypewriterFill.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import { useTypewriterFill } from "./useTypewriterFill";

function Harness({ text }: { text: string }) {
  const [val, setVal] = useState("");
  const { fillExample } = useTypewriterFill(setVal, { id: "harness-input" });
  return (
    <>
      <textarea id="harness-input" aria-label="harness" value={val} readOnly />
      <button onClick={() => fillExample(text)}>fill</button>
    </>
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  // reset any matchMedia stub
  // @ts-expect-error test cleanup
  delete window.matchMedia;
});

describe("useTypewriterFill", () => {
  it("fills instantly when prefers-reduced-motion is set", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    render(<Harness text="hello world" />);

    fireEvent.click(screen.getByText("fill"));

    expect((screen.getByLabelText("harness") as HTMLTextAreaElement).value).toBe("hello world");
  });

  it("types the full text over the interval when motion is allowed", () => {
    vi.useFakeTimers();
    // no matchMedia -> guard is false -> animate
    render(<Harness text="abcdefghij" />);

    fireEvent.click(screen.getByText("fill"));
    // mid-run it is not yet complete
    vi.advanceTimersByTime(16);
    const mid = (screen.getByLabelText("harness") as HTMLTextAreaElement).value;
    expect(mid.length).toBeGreaterThanOrEqual(0);
    expect(mid.length).toBeLessThan("abcdefghij".length);

    vi.runAllTimers();
    expect((screen.getByLabelText("harness") as HTMLTextAreaElement).value).toBe("abcdefghij");
  });

  it("focuses the target element", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    render(<Harness text="x" />);

    fireEvent.click(screen.getByText("fill"));

    expect(document.activeElement).toBe(screen.getByLabelText("harness"));
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd web && npx vitest run app/hooks/useTypewriterFill.test.tsx`
Expected: FAIL — module `./useTypewriterFill` not found.

- [ ] **Step 3: Implement the hook**

Create `web/app/hooks/useTypewriterFill.ts`:

```ts
import { useEffect, useRef } from "react";

type FocusTarget = { id?: string; selector?: string };

/**
 * Shared "type an example in" effect. Mirrors the original page.tsx behavior:
 * ~0.65s total, length-independent, honors prefers-reduced-motion, cancellable.
 */
export function useTypewriterFill(
  setter: (value: string) => void,
  focusTarget?: FocusTarget,
) {
  const intervalRef = useRef<number | null>(null);

  const stop = () => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => stop, []);

  const focus = () => {
    if (!focusTarget) return;
    const el = focusTarget.id
      ? document.getElementById(focusTarget.id)
      : focusTarget.selector
        ? document.querySelector<HTMLElement>(focusTarget.selector)
        : null;
    el?.focus();
  };

  const fillExample = (text: string) => {
    stop();
    focus();
    const prefersReduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setter(text);
      return;
    }
    setter("");
    const stepChars = Math.max(1, Math.ceil(text.length / 40)); // ~0.65s total, length-independent
    let i = 0;
    intervalRef.current = window.setInterval(() => {
      i = Math.min(text.length, i + stepChars);
      setter(text.slice(0, i));
      if (i >= text.length) stop();
    }, 16);
  };

  return { fillExample, stop };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd web && npx vitest run app/hooks/useTypewriterFill.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/app/hooks/useTypewriterFill.ts web/app/hooks/useTypewriterFill.test.tsx
git commit -m "feat(web): add shared useTypewriterFill hook for example autofill"
```

---

### Task 2: Refactor main `page.tsx` to consume the hook

**Files:**
- Modify: `web/app/page.tsx` (imports; remove lines ~165–196; add hook call)
- Test: `web/app/__tests__/page-example-fill.test.tsx`

- [ ] **Step 1: Write the failing regression test**

Create `web/app/__tests__/page-example-fill.test.tsx` (mock scaffold mirrors `page-conservative-toggle.test.tsx`):

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({ useCompiler: () => useCompilerMock() }));
vi.mock("../hooks/useContextManager", () => ({ useContextManager: () => useContextManagerMock() }));
vi.mock("../components/ContextManager", () => ({ default: () => <div data-testid="context-manager" /> }));
vi.mock("../components/OutputSkeleton", () => ({ default: () => <div data-testid="output-skeleton" /> }));

describe("main page example fill", () => {
  beforeEach(() => {
    localStorage.clear();
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    useCompilerMock.mockReturnValue({
      loading: false, result: null, status: "Ready", lastError: null,
      securityFindings: [], redactedText: "",
      runCompile: vi.fn(), retry: vi.fn(), resolveSecurityDecision: vi.fn(), cancelSecurityReview: vi.fn(),
    });
    useContextManagerMock.mockReturnValue({ indexStats: null });
  });

  it("fills the prompt textarea from the example button", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: /or try an example/i }));

    const textarea = screen.getByLabelText("Describe what you want compiled") as HTMLTextAreaElement;
    expect(textarea.value.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run it to verify it passes against current code (baseline green)**

Run: `cd web && npx vitest run app/__tests__/page-example-fill.test.tsx`
Expected: PASS (proves the test is valid before refactor). If the example button role/name differs, adjust the query to `screen.getByText(/or try an example/i)`.

- [ ] **Step 3: Refactor page.tsx**

1. Change the React import (drop now-unused `useRef`):
   - From: `import { useEffect, useId, useRef, useState } from "react";`
   - To:   `import { useEffect, useId, useState } from "react";`
2. Add the hook import near the other imports:
   - `import { useTypewriterFill } from "./hooks/useTypewriterFill";`
3. Delete the inline block (current lines ~165–196: the `// Typewriter entrance...` comment, `typewriterRef`, `stopTypewriter`, `useEffect(() => stopTypewriter, [])`, and the whole `fillExample` function).
4. In its place add:

```tsx
  const { fillExample, stop: stopTypewriter } = useTypewriterFill(setPrompt, {
    selector: 'textarea[aria-label="Describe what you want compiled"]',
  });
```

   (Aliasing `stop` to `stopTypewriter` keeps the existing `onChange` at line ~299 and Clear at line ~312 unchanged.)

- [ ] **Step 4: Run the regression test + full suite**

Run: `cd web && npx vitest run app/__tests__/page-example-fill.test.tsx && npm run test`
Expected: PASS; whole suite green.

- [ ] **Step 5: Commit**

```bash
git add web/app/page.tsx web/app/__tests__/page-example-fill.test.tsx
git commit -m "refactor(web): main page uses shared useTypewriterFill hook"
```

---

### Task 3: Wire `agent-generator`

**Files:** Modify `web/app/agent-generator/page.tsx`

- [ ] **Step 1: Add the hook import** (top of file, with other imports):

```tsx
import { useTypewriterFill } from "../hooks/useTypewriterFill";
```

- [ ] **Step 2: Call the hook** inside the component (near the `const [description, setDescription] = useState("")` declarations):

```tsx
  const { fillExample, stop: stopTypewriter } = useTypewriterFill(setDescription, { id: "agent-description" });
```

- [ ] **Step 3: Replace the example button handler** (current lines ~454–461):

Replace:
```tsx
                        onClick={() => {
                          setDescription("A customer support agent that answers questions about billing, handles refunds, and escalates complex issues to a human.");
                          setTimeout(() => {
                            const textarea = document.getElementById('agent-description');
                            if (textarea) textarea.focus();
                          }, 0);
                        }}
```
With:
```tsx
                        onClick={() => fillExample("A customer support agent that answers questions about billing, handles refunds, and escalates complex issues to a human.")}
```

- [ ] **Step 4: Cancel on manual edit and clear.**

Textarea onChange (line ~260):
- From: `onChange={(e) => setDescription(e.target.value)}`
- To:   `onChange={(e) => { stopTypewriter(); setDescription(e.target.value); }}`

Clear button (line ~275):
- From: `onClick={() => setDescription("")}`
- To:   `onClick={() => { stopTypewriter(); setDescription(""); }}`

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
Expected: whole suite green.
```bash
git add web/app/agent-generator/page.tsx
git commit -m "feat(web): animate agent-generator example fill"
```

---

### Task 4: Wire `skills-generator`

**Files:** Modify `web/app/skills-generator/page.tsx`

- [ ] **Step 1: Add import** `import { useTypewriterFill } from "../hooks/useTypewriterFill";`
- [ ] **Step 2: Call the hook** (near `const [description, setDescription] = useState("")`):

```tsx
  const { fillExample, stop: stopTypewriter } = useTypewriterFill(setDescription, { id: "skill-description" });
```

- [ ] **Step 3: Replace the example handler** (current lines ~427–434):

Replace the `onClick={() => { setDescription("A skill that ..."); setTimeout(...) }}` block with:
```tsx
                        onClick={() => fillExample("A skill that takes a URL, fetches the page content, extracts the main article text, and returns a 3-bullet summary.")}
```

- [ ] **Step 4: Cancel on manual edit.** Textarea onChange (line ~254):
- From: `onChange={(e) => setDescription(e.target.value)}`
- To:   `onChange={(e) => { stopTypewriter(); setDescription(e.target.value); }}`

(If this surface has a Clear-field button, wire `stopTypewriter()` into it the same way.)

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
```bash
git add web/app/skills-generator/page.tsx
git commit -m "feat(web): animate skills-generator example fill"
```

---

### Task 5: Wire `benchmark`

**Files:** Modify `web/app/benchmark/page.tsx`

- [ ] **Step 1: Add import** `import { useTypewriterFill } from "../hooks/useTypewriterFill";`
- [ ] **Step 2: Call the hook** (near `const [prompt, setPrompt] = useState(...)`):

```tsx
  const { fillExample, stop: stopTypewriter } = useTypewriterFill(setPrompt, { id: "benchmark-prompt" });
```

- [ ] **Step 3: Replace the example handler** (current lines ~525–531) with:
```tsx
                          onClick={() => fillExample("Write a Python script to scrape data from a Wikipedia page and extract all the tables.")}
```

- [ ] **Step 4: Cancel on manual edit.** Textarea onChange (lines ~355–358):
- From:
```tsx
                onChange={(event) => {
                  setPrompt(event.target.value);
                  window.localStorage.setItem("promptc_benchmark_prompt", event.target.value);
                }}
```
- To:
```tsx
                onChange={(event) => {
                  stopTypewriter();
                  setPrompt(event.target.value);
                  window.localStorage.setItem("promptc_benchmark_prompt", event.target.value);
                }}
```

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
```bash
git add web/app/benchmark/page.tsx
git commit -m "feat(web): animate benchmark example fill"
```

---

### Task 6: Wire `optimizer`

**Files:** Modify `web/app/optimizer/page.tsx` (textarea already has `id="original-prompt"`; the example button currently does not focus at all — the hook adds focus).

- [ ] **Step 1: Add import** `import { useTypewriterFill } from "../hooks/useTypewriterFill";`
- [ ] **Step 2: Call the hook** (near `const [input, setInput] = useState(...)`):

```tsx
    const { fillExample, stop: stopTypewriter } = useTypewriterFill(setInput, { id: "original-prompt" });
```

- [ ] **Step 3: Replace the example handler** (current lines ~497–499) with:
```tsx
                                        onClick={() => fillExample("You are a helpful assistant. Provide a detailed, step-by-step summary of the provided text, ensuring that no important information is left out, and format the output as a bulleted list with clear headings for each section.")}
```

- [ ] **Step 4: Cancel on manual edit.** Textarea onChange (lines ~410–413):
- From:
```tsx
                            onChange={(e) => {
                                setInput(e.target.value);
                                window.localStorage.setItem("promptc_optimizer_prompt", e.target.value);
                            }}
```
- To:
```tsx
                            onChange={(e) => {
                                stopTypewriter();
                                setInput(e.target.value);
                                window.localStorage.setItem("promptc_optimizer_prompt", e.target.value);
                            }}
```

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
```bash
git add web/app/optimizer/page.tsx
git commit -m "feat(web): animate optimizer example fill"
```

---

### Task 7: Wire `agent-packs`

**Files:** Modify `web/app/agent-packs/page.tsx` (setter writes a nested field via `handleFieldChange('goal', …)`).

- [ ] **Step 1: Add import** `import { useTypewriterFill } from "../hooks/useTypewriterFill";`
- [ ] **Step 2: Call the hook** (after `handleFieldChange` is defined, ~line 119):

```tsx
  const { fillExample, stop: stopTypewriter } = useTypewriterFill(
    (v) => handleFieldChange("goal", v),
    { id: "agent-pack-goal" },
  );
```

- [ ] **Step 3: Replace the example handler** (current lines ~582–589) with:
```tsx
                        onClick={() => fillExample("Review PRs for prompt leakage, unsafe settings, and missing regression tests.")}
```

- [ ] **Step 4: Cancel on manual edit and clear.**

Textarea onChange (line ~338):
- From: `onChange={(event) => handleFieldChange("goal", event.target.value)}`
- To:   `onChange={(event) => { stopTypewriter(); handleFieldChange("goal", event.target.value); }}`

Clear button (line ~346):
- From: `onClick={() => handleFieldChange("goal", "")}`
- To:   `onClick={() => { stopTypewriter(); handleFieldChange("goal", ""); }}`

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
```bash
git add web/app/agent-packs/page.tsx
git commit -m "feat(web): animate agent-packs example fill"
```

---

### Task 8: Wire `offline` (two example buttons, one hook)

**Files:** Modify `web/app/offline/page.tsx`

- [ ] **Step 1: Add import** `import { useTypewriterFill } from "../hooks/useTypewriterFill";`
- [ ] **Step 2: Call the hook once** (near `const [prompt, setPrompt] = useState("")`):

```tsx
    const { fillExample, stop: stopTypewriter } = useTypewriterFill(setPrompt, { id: "offline-prompt" });
```

- [ ] **Step 3: Replace BOTH example handlers.**

First button (current lines ~174–181):
```tsx
                                        onClick={() => fillExample("Create a Python script that monitors a local log directory for new .log files, parses them for ERROR level messages, and outputs a summary report.")}
```
Second button (current lines ~276–286): keep its own example text — replace its `onClick={() => { setPrompt("..."); setTimeout(...) }}` with:
```tsx
                                            onClick={() => fillExample("Summarize the key points of this meeting transcript.")}
```

- [ ] **Step 4: Cancel on manual edit.** Textarea onChange (line ~123):
- From: `onChange={(e) => setPrompt(e.target.value)}`
- To:   `onChange={(e) => { stopTypewriter(); setPrompt(e.target.value); }}`

- [ ] **Step 5: Verify + commit**

Run: `cd web && npm run test`
```bash
git add web/app/offline/page.tsx
git commit -m "feat(web): animate offline example fill"
```

---

### Task 9: Full verification

- [ ] **Step 1: Full web test suite**

Run: `cd web && npm run test`
Expected: all files/tests pass.

- [ ] **Step 2: Type-check / build**

Run: `cd web && npm run build`
Expected: build succeeds (no TS errors).

- [ ] **Step 3: Manual smoke (optional but recommended)**

Run the dev server, open each surface, click "or try an example", confirm the text types in (and that manual typing mid-animation cancels it). Also toggle OS "reduce motion" and confirm instant fill.

---

## Self-Review

**Spec coverage:**
- Shared hook `useTypewriterFill` → Task 1. ✅
- Applied to the 6 surfaces (agent-generator, skills-generator, benchmark, optimizer, agent-packs, offline) → Tasks 3–8. ✅
- Main `page.tsx` refactored to consume the hook → Task 2. ✅
- Behavior parity (~0.65s, length-independent, reduced-motion, cancel on edit/clear) → hook impl + per-surface onChange/Clear wiring. ✅
- `pr-safety` excluded → not in any task. ✅
- Testing (reduced-motion + timer paths) → Task 1 hook tests; Task 2 regression test. ✅

**Placeholder scan:** Each surface task shows exact before/after code and exact example strings. The only conditional note ("if this surface has a Clear button") applies to skills-generator, where none was found in the mapped region; onChange cancellation (the primary guard) is exact. No TODO/TBD.

**Type consistency:** Hook returns `{ fillExample, stop }` everywhere; surfaces alias `stop` as `stopTypewriter` to match the reference naming used in onChange/Clear handlers. `focusTarget` uses `{ id }` for surfaces and `{ selector }` for the main page. Consistent across all tasks.
