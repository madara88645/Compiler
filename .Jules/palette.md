## $(date +%Y-%m-%d) - Padding for absolutely positioned buttons
**Learning:** When adding conditionally rendered, absolutely positioned buttons (like 'Clear') over textareas or inputs, failing to add right padding to the underlying input will cause user text to flow underneath and be obscured by the button.
**Action:** Always add sufficient right padding (e.g., `pr-14`) to textareas/inputs that contain absolutely positioned overlay elements to ensure the content remains readable.
