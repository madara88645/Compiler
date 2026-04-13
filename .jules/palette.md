## 2025-04-06 - Utility Button Focus States
**Learning:** Icon-only or utility buttons (like "Copy" or accordion toggles) often miss `focus-visible` states because they don't look like primary actions, making them inaccessible to keyboard users navigating via Tab.
**Action:** When adding utility buttons, always explicitly define `focus-visible:outline-none` and `focus-visible:ring-2` (or `ring-1`) with the appropriate brand color.

## 2024-04-09 - Polish RAG Search Panel UX
**Learning:** When users click an action like 'Insert into Prompt', visual feedback (such as a success toast) is critical so they aren't left wondering if it worked. Also, clearable inputs (with an 'X' button) significantly speed up the iterative search workflow compared to forcing the user to manually backspace long queries.
**Action:** Add clearable (X) buttons inside text inputs intended for frequent querying/searching, and always include brief visual confirmation notifications (like toasts) when an action completes without an obvious immediate visual state change.

## 2025-04-10 - Empty State Call-to-Actions
**Learning:** Empty states without Call-to-Action (CTA) buttons create friction, especially when the required action button is visually distant (e.g., in a top-right corner). Adding an inline CTA directly in the empty state significantly improves UX by making the next step obvious and easily accessible.
**Action:** When designing or refactoring empty states, always include a clear CTA button inline if the state requires user action to change. Ensure the CTA has descriptive disabled states/tooltips if conditions aren't met (e.g., missing input).
