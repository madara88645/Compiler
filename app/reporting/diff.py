"""
Text Processing Utility for Diff Generation.
Provides functionality to compute and render HTML diffs between text strings.
"""

import html
import difflib


def generate_html_diff(old_text: str, new_text: str) -> str:
    """
    Generate an HTML string highlighting differences between two texts.

    Uses character-level diffing to show precise changes.
    - Removed text is wrapped in <span class="diff-removed">
    - Added text is wrapped in <span class="diff-added">

    Args:
        old_text: The original prompt text.
        new_text: The modified prompt text.

    Returns:
        A safe HTML string with diff classes applied.
        Wrapped in a <pre> block for whitespace preservation is expected by the caller or CSS.
        But here we will just return the content with spans, and newlines preserved.
        To ensure correct display, we'll convert newlines to <br> if we weren't using <pre>.
        However, for prompt diffs, <pre> wrap in the UI is standard.
        Let's allow the caller to wrap in <pre>. We will just return the inner HTML.
    """
    # 1. Handle edge cases
    if old_text == new_text:
        return html.escape(old_text)

    if not old_text:
        return f'<span class="diff-added">{html.escape(new_text)}</span>'

    if not new_text:
        return f'<span class="diff-removed">{html.escape(old_text)}</span>'

    # 2. Compute Diff (Character level usually best for dense prompts)
    matcher = difflib.SequenceMatcher(None, old_text, new_text)
    output = []

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            # Unchanged text
            text = old_text[a0:a1]
            output.append(html.escape(text))

        elif opcode == "insert":
            # New text added
            text = new_text[b0:b1]
            output.append(f'<span class="diff-added">{html.escape(text)}</span>')

        elif opcode == "delete":
            # Old text removed
            text = old_text[a0:a1]
            output.append(f'<span class="diff-removed">{html.escape(text)}</span>')

        elif opcode == "replace":
            # Text changed
            removed = old_text[a0:a1]
            added = new_text[b0:b1]
            output.append(f'<span class="diff-removed">{html.escape(removed)}</span>')
            output.append(f'<span class="diff-added">{html.escape(added)}</span>')

    return "".join(output)
