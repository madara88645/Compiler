## 2024-04-09 - Polish RAG Search Panel UX
**Learning:** When users click an action like 'Insert into Prompt', visual feedback (such as a success toast) is critical so they aren't left wondering if it worked. Also, clearable inputs (with an 'X' button) significantly speed up the iterative search workflow compared to forcing the user to manually backspace long queries.
**Action:** Add clearable (X) buttons inside text inputs intended for frequent querying/searching, and always include brief visual confirmation notifications (like toasts) when an action completes without an obvious immediate visual state change.

## 2025-04-06 - Utility Button Focus States
**Learning:** Icon-only or utility buttons (like "Copy" or accordion toggles) often miss `focus-visible` states because they don't look like primary actions, making them inaccessible to keyboard users navigating via Tab.
**Action:** When adding utility buttons, always explicitly define `focus-visible:outline-none` and `focus-visible:ring-2` (or `ring-1`) with the appropriate brand color.

## 2025-04-10 - Empty State Call-to-Actions
**Learning:** Empty states without Call-to-Action (CTA) buttons create friction, especially when the required action button is visually distant (e.g., in a top-right corner). Adding an inline CTA directly in the empty state significantly improves UX by making the next step obvious and easily accessible.
**Action:** When designing or refactoring empty states, always include a clear CTA button inline if the state requires user action to change. Ensure the CTA has descriptive disabled states/tooltips if conditions aren't met (e.g., missing input).

## 2025-04-10 - Explicit Button Types
**Learning:** Buttons without explicit `type` attributes default to `type="submit"` in standard HTML parsing. This can inadvertently trigger unexpected page reloads or form submissions across the application when a simple interactive button is clicked.
**Action:** Always add `type="button"` to any `<button>` component in the frontend unless it is explicitly intended to submit a form.
## 2024-04-20 - Adding Keyboard Focus States to Buttons
**Learning:** Several utility buttons in the Context Manager components lacked `focus-visible` styles, making keyboard navigation difficult to track. Using Tailwind's `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500` is an effective, reusable pattern for resolving this across the application without breaking custom hover styles.
**Action:** Next time I build or refactor interactive elements (especially text-based links acting as buttons or small UI toggles), I should proactively add the standard focus rings so keyboard users aren't left guessing where they are.
## 2025-04-24 - Accessibility for input elements without visible labels
**Learning:** For interactive elements like `<textarea>` that function as central input areas in full-page editors but lack a dedicated `<label>`, it is crucial to manually add an `aria-label` attribute. Without this, screen readers will announce the element generically (e.g., "text area, blank"), leaving visually impaired users without context on what the input is for.
**Action:** When creating or reviewing form inputs without explicit visible `<label>` tags, proactively add an `aria-label` to provide the necessary context.

## 2026-04-24 - Added Keyboard Focus States to Floating Copy Buttons\n**Learning:** Floating copy buttons that appear conditionally or use absolute positioning often lack `focus-visible` states, rendering them inaccessible to keyboard-only users who cannot easily discover them via tab navigation.\n**Action:** When adding utility or floating buttons, always explicitly define `focus-visible:outline-none` and `focus-visible:ring-2` (or `ring-1`) with the appropriate brand color.

## 2024-05-15 - [Add aria-controls to ExportPanel buttons]
**Learning:** For collapsible content, buttons with `aria-expanded` must also have an `aria-controls` attribute linking them to the content container's ID for screen readers.
**Action:** When creating expanding/collapsing UI panels, generate a unique ID (e.g. via `useId`) to link the toggle control directly to its target content.
