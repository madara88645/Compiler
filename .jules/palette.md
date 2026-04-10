## 2025-04-06 - Utility Button Focus States
**Learning:** Icon-only or utility buttons (like "Copy" or accordion toggles) often miss `focus-visible` states because they don't look like primary actions, making them inaccessible to keyboard users navigating via Tab.
**Action:** When adding utility buttons, always explicitly define `focus-visible:outline-none` and `focus-visible:ring-2` (or `ring-1`) with the appropriate brand color.

## 2024-04-09 - Polish RAG Search Panel UX
**Learning:** When users click an action like 'Insert into Prompt', visual feedback (such as a success toast) is critical so they aren't left wondering if it worked. Also, clearable inputs (with an 'X' button) significantly speed up the iterative search workflow compared to forcing the user to manually backspace long queries.
**Action:** Add clearable (X) buttons inside text inputs intended for frequent querying/searching, and always include brief visual confirmation notifications (like toasts) when an action completes without an obvious immediate visual state change.
