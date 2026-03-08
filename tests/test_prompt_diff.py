import pytest

from app.prompt_diff import PromptComparison


@pytest.fixture
def comparator():
    """Fixture providing a PromptComparison instance without running __init__."""
    return PromptComparison.__new__(PromptComparison)


def test_generate_diff_identical_texts(comparator):
    """Test generating a diff for identical texts."""
    text = "This is a prompt.\nIt has two lines."
    diff = comparator.generate_diff(text, text)

    # Empty diff or just no content changes
    assert diff == []


def test_generate_diff_single_line_change(comparator):
    """Test generating a diff when a single line is changed."""
    text1 = "This is the first line.\nThis is the second line."
    text2 = "This is the first line.\nThis is the MODIFIED second line."

    diff = comparator.generate_diff(text1, text2)

    # The output should contain standard unified diff headers
    assert "--- prompt1" in diff
    assert "+++ prompt2" in diff

    # It should have a hunk header
    assert any(line.startswith("@@ ") for line in diff)

    # It should show the removed and added lines
    assert "-This is the second line." in diff
    assert "+This is the MODIFIED second line." in diff


def test_generate_diff_added_and_removed_lines(comparator):
    """Test generating a diff with multiple additions and removals."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine 2.5\nLine 3"

    diff = comparator.generate_diff(text1, text2)

    assert "-Line 2\n" in diff
    assert "+Line 2.5\n" in diff


def test_generate_diff_context_lines(comparator):
    """Test that adjusting the context_lines argument affects the output."""
    # A text with many lines
    text1 = "L1\nL2\nL3\nL4\nL5\nL6\nL7\nL8\nL9"
    # Change happens in the middle
    text2 = "L1\nL2\nL3\nL4\nMODIFIED\nL6\nL7\nL8\nL9"

    # Default context is usually 3
    diff_default = comparator.generate_diff(text1, text2, context_lines=3)

    # Context of 1
    diff_small_context = comparator.generate_diff(text1, text2, context_lines=1)

    # The default context should include L2, L3, L4 (before) and L6, L7, L8 (after)
    assert " L2\n" in diff_default
    assert " L8\n" in diff_default

    # The small context should NOT include L2 or L8
    assert " L2\n" not in diff_small_context
    assert " L8\n" not in diff_small_context
    assert " L4\n" in diff_small_context
    assert " L6\n" in diff_small_context


def test_generate_diff_empty_texts(comparator):
    """Test generating diffs with empty strings."""
    # Both empty
    assert comparator.generate_diff("", "") == []

    # One empty
    diff = comparator.generate_diff("Some content", "")
    assert "--- prompt1" in diff
    assert "-Some content" in diff

    diff2 = comparator.generate_diff("", "Some content")
    assert "+++ prompt2" in diff2
    assert "+Some content" in diff2


def test_get_prompt_comparison_singleton():
    """Test that get_prompt_comparison returns a singleton instance."""
    from app.prompt_diff import get_prompt_comparison

    # Get the instance twice
    instance1 = get_prompt_comparison()
    instance2 = get_prompt_comparison()

    # Verify they are the exact same object (singleton pattern)
    assert instance1 is instance2

    # Verify it's actually the correct type
    assert isinstance(instance1, PromptComparison)
