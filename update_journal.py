import os

journal_entry = """## 2024-07-26 - Dynamic disabled button tooltips improve multi-field form UX
**Learning:** For forms with multiple required fields, a generic "Fill in all fields" tooltip on a disabled submit button creates friction, as users must manually check which fields they missed.
**Action:** Always dynamically calculate and display exactly which fields are missing in the button's `title` attribute (e.g., "Missing: Title, Description") to provide immediate, actionable feedback.
"""

journal_path = ".jules/palette.md"
os.makedirs(os.path.dirname(journal_path), exist_ok=True)
with open(journal_path, "a") as f:
    f.write(journal_entry + "\n")
