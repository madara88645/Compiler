## 2024-03-14 - Fix Hidden Interactive Elements
**Learning:** Hiding buttons with `opacity-0` and only showing them on hover (like `group-hover:opacity-100`) creates a keyboard accessibility trap. Screen reader and keyboard-only users can focus the element, but cannot see it because it remains invisible when focused.
**Action:** Always pair `opacity-0 group-hover:opacity-100` with an explicit focus state like `focus-visible:opacity-100 focus-visible:ring-2` to ensure the element becomes visible when navigated to via keyboard.
