💡 What:
- Applied `aria-live="polite"` directly to the main "Copy" interactive `<button>` elements in the Agent and Skills Generator pages and their respective export panels.
- Addressed the missing visual description context on the `skills-generator` page by connecting the `textarea` directly to its accompanying description helper text using `aria-describedby` and a uniquely assigned `id`.
- Removed a duplicate, unused visually hidden `<span className="sr-only">` that was intended to fire the "Copied!" event inside the Copy buttons, relying instead on the newly attached `aria-live` root button trait to handle it cleanly.

🎯 Why:
The "Copied!" feedback state is critical. However, screen readers sometimes miss state changes applied only to deeply nested, hidden child elements (such as `sr-only` spans). Applying `aria-live` at the primary button level creates a more robust live region. For the text inputs, the helper text context "Describe the skill's purpose..." was unreadable for non-visual users navigating explicitly by form inputs.

📸 Before/After:
No visible visual changes. The modifications are isolated to the underlying accessible semantics.

♿ Accessibility:
- Replaced `<span aria-live="polite">` with a root `<button aria-live="polite">`.
- Associated `aria-describedby="skill-description-help"` explicitly with the Skill Generator's `<textarea>`, ensuring the text `<p id="skill-description-help">...` is read aloud.
