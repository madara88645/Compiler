## 2024-05-20 - Ensure visual feedback for Copy to Clipboard actions
**Learning:** Adding a toast notification using a library like `sonner` is a crucial micro-interaction for copy-to-clipboard functionality. Users lack confidence when clicking a copy button without visual confirmation, and this small change significantly improves the perceived reliability of the UI.
**Action:** Always verify that interactive elements, especially non-destructive actions like copying or sharing, have immediate visual feedback in the form of a toast or inline confirmation.
