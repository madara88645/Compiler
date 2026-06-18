## 2024-05-20 - Ensure visual feedback for Copy to Clipboard actions
**Learning:** Adding a toast notification using a library like `sonner` is a crucial micro-interaction for copy-to-clipboard functionality. Users lack confidence when clicking a copy button without visual confirmation, and this small change significantly improves the perceived reliability of the UI.
**Action:** Always verify that interactive elements, especially non-destructive actions like copying or sharing, have immediate visual feedback in the form of a toast or inline confirmation.
## 2024-05-26 - Avoid Redundant `aria-disabled` Attributes
**Learning:** Adding an `aria-disabled` attribute to a button that already uses the native HTML `disabled` attribute is redundant and considered an ARIA anti-pattern. Native `disabled` inherently communicates the state to assistive technologies and removes the element from the tab order.
**Action:** When improving loading states for buttons, rely on the native `disabled` attribute and use `aria-busy={loading}` to inform screen readers of the active process without duplicating the disabled state.
## 2024-05-30 - Empty States Call-to-Action
**Learning:** Including an 'or try an example' call-to-action button that populates the input field solves the 'blank canvas' UX problem by explicitly demonstrating the expected input format to users.
**Action:** When designing empty states for text areas and generative tools, include an 'or try an example' call-to-action button that populates the input field.
## 2024-06-01 - Avoid duplicate ARIA attributes in React
**Learning:** Adding duplicate props like `aria-busy={downloading}` and `aria-busy={loading}` causes React build failures due to `react/jsx-no-duplicate-props`. Even though one of the values might be correct logically, both cannot exist on the same element.
**Action:** When adding accessibility attributes like `aria-busy` to existing elements, ensure there isn't already one present, or replace the existing one with the correct value if necessary.
## 2024-06-03 - Mutually Exclusive Button ARIA Grouping
**Learning:** When using standard `<button>` tags to create mutually exclusive selection groups (like toggle groups or choice cards), relying solely on visual styling is insufficient for accessibility. Screen readers will treat them as independent, unrelated buttons without state.
**Action:** Always wrap the buttons in a container with `role="radiogroup"` and a descriptive `aria-label`, and add `role="radio"` and `aria-checked={active}` to each button. This ensures the component is properly announced as a radio group and communicates selection state correctly.
## 2024-06-17 - Add Clear Button to Input Forms
**Learning:** For generative text inputs where users often paste large blocks of text, missing a quick way to clear the input creates friction. Users have to manually select all text and delete it.
**Action:** Always consider adding a "Clear" button (with proper `type="button"`, `aria-label`, and `title` attributes) to large input fields (like textareas) to improve usability.
