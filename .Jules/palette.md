## 2026-03-08 - Inaccessible div-based toggles
**Learning:** The app uses custom div-based toggles for boolean settings (like 'Multi-Agent Swarm' and 'Example Code'), which are completely invisible to screen readers and inaccessible via keyboard navigation.
**Action:** Always implement custom toggles using `<button role="switch">`, adding `aria-checked`, `aria-labelledby`, `aria-describedby`, and ensure they have visible focus states (e.g., `focus-visible:ring-2`).
