## 2024-03-06 - Accessible Icon-Only Navigation
**Learning:** Found an accessibility issue in the main Sidebar navigation (`web/app/components/Sidebar.tsx`) where icon-only links lacked proper labels, active state indicators (`aria-current`), and keyboard focus rings. Also, emoji icons were not hidden from screen readers.
**Action:** Implemented a standard accessible pattern: added `aria-label` to the links, `aria-current="page"` to indicate active status, wrapped emojis in `<span aria-hidden="true">`, applied `focus-visible` classes for keyboard navigation, and added `aria-hidden="true"` to visual tooltips to prevent redundant announcements. This pattern should be applied to any future icon-only navigation components.

## 2024-03-07 - Custom Tooltip Keyboard Accessibility
**Learning:** Custom interactive tooltips (like in `InfoButton.tsx`) that rely only on `onMouseEnter` and `onMouseLeave` are completely invisible to keyboard users. Without explicit focus handling, they cannot access the information provided in the tooltip.
**Action:** Always pair mouse hover events with explicit `onFocus` and `onBlur` handlers for custom tooltips. Additionally, add `focus-visible` classes to the trigger element to clearly indicate focus, and ensure proper ARIA attributes (`role="tooltip"` on the tooltip content and `aria-expanded` on the trigger).
