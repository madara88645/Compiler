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


def test_get_diff_stats_identical_texts(comparator):
    """Test get_diff_stats with identical texts."""
    text = "Line 1\nLine 2\nLine 3"
    stats = comparator.get_diff_stats(text, text)

    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 0
    assert stats["lines_same"] == 3
    assert stats["total_lines_1"] == 3
    assert stats["total_lines_2"] == 3
    assert stats["similarity"] == 100.0


def test_get_diff_stats_completely_different(comparator):
    """Test get_diff_stats with completely different texts."""
    text1 = "Apple"
    text2 = "Orange"
    stats = comparator.get_diff_stats(text1, text2)

    # They are considered a replacement by SequenceMatcher
    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 1
    assert stats["lines_same"] == 0
    assert stats["total_lines_1"] == 1
    assert stats["total_lines_2"] == 1
    # similarity won't be exactly 0.0 for Apple vs Orange (SequenceMatcher ratio)
    assert 0.0 <= stats["similarity"] < 20.0


def test_get_diff_stats_insertions_and_deletions(comparator):
    """Test get_diff_stats with insertions and deletions."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine 2.5\nLine 3\nLine 4"
    stats = comparator.get_diff_stats(text1, text2)

    # "Line 2" replaced by "Line 2.5" is seen as a changed line (replace opcode).
    # Then "Line 4" is added (insert opcode).
    assert stats["lines_added"] == 1  # Line 4
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 1  # Line 2 replaced by Line 2.5
    assert stats["lines_same"] == 2  # Line 1, Line 3
    assert stats["total_lines_1"] == 3
    assert stats["total_lines_2"] == 4
    # similarity should be > 0 and < 100
    assert 0 < stats["similarity"] < 100.0


def test_get_diff_stats_replacements(comparator):
    """Test get_diff_stats with line replacements."""
    text1 = "A\nB\nC\nD"
    text2 = "A\nX\nY\nD"
    stats = comparator.get_diff_stats(text1, text2)

    # 'B\nC' replaced by 'X\nY' -> max(2, 2) = 2 changed lines
    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 2
    assert stats["lines_same"] == 2
    assert stats["total_lines_1"] == 4
    assert stats["total_lines_2"] == 4


def test_get_diff_stats_empty_texts(comparator):
    """Test get_diff_stats with empty strings."""
    # Both empty
    stats_empty = comparator.get_diff_stats("", "")
    assert stats_empty["lines_added"] == 0
    assert stats_empty["lines_removed"] == 0
    assert stats_empty["lines_changed"] == 0
    assert stats_empty["lines_same"] == 0
    assert stats_empty["total_lines_1"] == 0
    assert stats_empty["total_lines_2"] == 0
    assert stats_empty["similarity"] == 100.0

    # One empty
    stats_one_empty = comparator.get_diff_stats("Content", "")
    assert stats_one_empty["lines_added"] == 0
    assert stats_one_empty["lines_removed"] == 1
    assert stats_one_empty["lines_changed"] == 0
    assert stats_one_empty["lines_same"] == 0
    assert stats_one_empty["total_lines_1"] == 1
    assert stats_one_empty["total_lines_2"] == 0
    assert stats_one_empty["similarity"] == 0.0

    stats_other_empty = comparator.get_diff_stats("", "Content")
    assert stats_other_empty["lines_added"] == 1
    assert stats_other_empty["lines_removed"] == 0
    assert stats_other_empty["lines_changed"] == 0
    assert stats_other_empty["lines_same"] == 0
    assert stats_other_empty["total_lines_1"] == 0
    assert stats_other_empty["total_lines_2"] == 1
    assert stats_other_empty["similarity"] == 0.0
