## 2024-05-20 - Ensure visual feedback for Copy to Clipboard actions
**Learning:** Adding a toast notification using a library like `sonner` is a crucial micro-interaction for copy-to-clipboard functionality. Users lack confidence when clicking a copy button without visual confirmation, and this small change significantly improves the perceived reliability of the UI.
**Action:** Always verify that interactive elements, especially non-destructive actions like copying or sharing, have immediate visual feedback in the form of a toast or inline confirmation.
## 2024-05-26 - Avoid Redundant `aria-disabled` Attributes
**Learning:** Adding an `aria-disabled` attribute to a button that already uses the native HTML `disabled` attribute is redundant and considered an ARIA anti-pattern. Native `disabled` inherently communicates the state to assistive technologies and removes the element from the tab order.
**Action:** When improving loading states for buttons, rely on the native `disabled` attribute and use `aria-busy={loading}` to inform screen readers of the active process without duplicating the disabled state.
## 2024-05-30 - Empty States Call-to-Action
**Learning:** Including an 'or try an example' call-to-action button that populates the input field solves the 'blank canvas' UX problem by explicitly demonstrating the expected input format to users.
**Action:** When designing empty states for text areas and generative tools, include an 'or try an example' call-to-action button that populates the input field.
## 2024-05-31 - Add aria-busy to loading buttons
**Learning:** Found that while buttons were being visually and functionally disabled via `disabled={loading}`, screen readers were not being explicitly informed of the loading state. This is an accessibility issue for async actions across multiple pages.
**Action:** Use `aria-busy={loading}` along with `disabled` states for asynchronous actions like fetching, processing, or generating. Do not use `aria-disabled` if the native `disabled` attribute is already correctly managing focus and click prevention, as it's a known ARIA anti-pattern.
