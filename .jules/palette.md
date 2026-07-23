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
## 2024-05-14 - Use visually hidden element for aria-live instead of button state change
**Learning:** Placing `aria-live="polite"` directly on a button whose label changes (e.g., "Copy" to "Copied!") can lead to flaky screen reader announcements. The screen reader may only read the static `aria-label` or fail to notice the internal text mutation correctly because the focus is on the element being mutated.
**Action:** The most robust way to announce a copy status change is to use a separate, visually hidden element (e.g., `<span className="sr-only" aria-live="polite">{copied ? 'Copied to clipboard' : ''}</span>`) rather than placing `aria-live` directly on the mutating button. Additionally, ensure that buttons do not have static `aria-labels` that override dynamic content unless intentionally designed that way.
## 2024-06-27 - Add Clear Button to Input Forms (Re-applied)
**Learning:** For generative text inputs where users often paste large blocks of text, missing a quick way to clear the input creates friction. This applies to multiple areas of the app, like the PR Safety feature.
**Action:** Always consider adding a "Clear" button (with proper `type="button"`, `aria-label`, and `title` attributes) to large input fields (like textareas) to improve usability. Make sure to wrap the `<textarea>` in a `<div className="relative group">` to allow absolute positioning of the clear button inside it.
## 2024-05-19 - Added example button to offline heuristics tool
**Learning:** The "or try an example" button pattern used in the Prompt Compiler and Agent Generator tools is highly effective at reducing friction for new users facing an empty text area. The offline heuristics tool was missing this helpful empty state.
**Action:** Replicate the exact UX pattern (a muted, subtle button that populates the textarea and focuses it) in `web/app/offline/page.tsx` when the input is empty.
## 2024-11-20 - Adding dynamic copy state announcements and explicit helper text descriptions
**Learning:** For dynamic indicator elements (like "Copied!" buttons), applying `aria-live="polite"` directly to the main element itself provides better and more robust screen reader support across implementations than applying it to a visually hidden child span. For complex empty states, tying descriptions properly to `<textarea>` components using `aria-describedby` provides critical context that the generic `aria-label` lacks.
**Action:** When creating new components that toggle their state momentarily (e.g., to confirm an action like copying), apply `aria-live="polite"` to the button element itself and remove unnecessary child elements trying to mimic this. Always connect helper texts to `textarea` or `input` boxes using `aria-describedby` when an explicit visual layout description exists.
## 2024-07-04 - Screen reader associations for input elements
**Learning:** Found that multiple Textarea input components in the application had `aria-label`s, but had separate label elements meant to serve as their descriptive label, often containing a `sr-only` class. These textual descriptions were not being properly associated with the textareas.
**Action:** Use unique `id` attributes on the label elements and `aria-labelledby` on the textarea inputs to associate them properly. Also, assign unique `id`s to the helper text and use `aria-describedby` to link them to the textareas.
## 2025-02-13 - Add padding to prevent text overlap with absolutely positioned buttons
**Learning:** When textareas or inputs have absolutely positioned interactive elements (like a "Clear" button) floating over them, users can experience friction if long text flows underneath the button, making it unreadable or unclickable.
**Action:** Always ensure the underlying text input has sufficient right padding (e.g., `pr-14` in Tailwind) so the text wraps naturally without overlapping the absolutely positioned elements on the right side.
## 2024-05-18 - Add titles explaining disabled button states
**Learning:** Default disabled action buttons (like "Generate Agent", "Analyze PR") provided no context for why they were disabled, leaving users guessing which inputs were required before the form was considered valid.
**Action:** Implemented dynamic `title` attributes on all disabled primary action buttons across the generator pages that conditionally switch between explanatory text ("Enter a description first...") when disabled and the normal CTA when enabled. This improves screen reader context and provides helpful tooltips on hover.
## 2024-07-16 - Replace native tooltips with styled CSS tooltips
**Learning:** Native OS-level tooltips (using the title attribute) appear on a delay and can feel inconsistent or unpolished in modern web interfaces, especially for primary navigation like sidebars.
**Action:** Replace title attributes with custom CSS tooltips (e.g., using Tailwind's group-hover utilities) for immediate, consistent, and styled visual feedback on hover and focus.
## 2024-05-19 - Specific Tooltips for Disabled Submit Buttons
**Learning:** Generic tooltips (e.g. "Enter a description first") on disabled submit buttons leave users guessing which exact field is missing, especially on forms with multiple inputs.
**Action:** When a form submission or action button is disabled due to missing inputs or incomplete state, improve UX and accessibility by explicitly naming the missing required fields in the tooltip (e.g., "Missing required fields: PR Title, Changed Files"). This is especially important for forms with many inputs like the PR Safety feature. For Playwright tests, note that native HTML tooltips (`title` attributes) are OS-level overlays and won't appear in screenshots; verify them by querying DOM attributes directly.
