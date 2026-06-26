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


def test_get_diff_stats_empty_texts(comparator):
    """Test get_diff_stats with empty texts."""
    stats = comparator.get_diff_stats("", "")

    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 0
    assert stats["lines_same"] == 0
    assert stats["total_lines_1"] == 0
    assert stats["total_lines_2"] == 0
    assert stats["similarity"] == 100.0


def test_get_diff_stats_added_lines(comparator):
    """Test get_diff_stats with added lines."""
    text1 = "Line 1\nLine 3"
    text2 = "Line 1\nLine 2\nLine 3"
    stats = comparator.get_diff_stats(text1, text2)

    assert stats["lines_added"] == 1
    assert stats["lines_removed"] == 0
    assert stats["lines_changed"] == 0
    assert stats["lines_same"] == 2
    assert stats["total_lines_1"] == 2
    assert stats["total_lines_2"] == 3


def test_get_diff_stats_removed_lines(comparator):
    """Test get_diff_stats with removed lines."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine 3"
    stats = comparator.get_diff_stats(text1, text2)

    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 1
    assert stats["lines_changed"] == 0
    assert stats["lines_same"] == 2
    assert stats["total_lines_1"] == 3
    assert stats["total_lines_2"] == 2


def test_get_diff_stats_changed_lines(comparator):
    """Test get_diff_stats with changed lines."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine MODIFIED\nLine 3"
    stats = comparator.get_diff_stats(text1, text2)

    # In SequenceMatcher, changing a line typically results in a 'replace' operation
    # where lines are removed and added, or a single 'replace' if lengths are equal
    assert stats["lines_changed"] == 1
    assert stats["lines_added"] == 0
    assert stats["lines_removed"] == 0
    assert stats["lines_same"] == 2
    assert stats["total_lines_1"] == 3
    assert stats["total_lines_2"] == 3


def test_get_prompt_comparison_singleton(monkeypatch):
    """Test that get_prompt_comparison returns a singleton instance."""
    from unittest.mock import MagicMock

    import app.prompt_diff
    from app.prompt_diff import get_prompt_comparison

    # Stub out manager factories so constructing PromptComparison() never touches on-disk DBs
    monkeypatch.setattr(app.prompt_diff, "get_history_manager", MagicMock())
    monkeypatch.setattr(app.prompt_diff, "get_favorites_manager", MagicMock())

    # Reset the singleton so this test always exercises the initialization path,
    # regardless of test execution order (monkeypatch restores the original value after the test)
    monkeypatch.setattr(app.prompt_diff, "_prompt_comparison", None)

    # Get the instance twice
    instance1 = get_prompt_comparison()
    instance2 = get_prompt_comparison()

    # Verify they are the exact same object (singleton pattern)
    assert instance1 is instance2

    # Verify it's actually the correct type
    assert isinstance(instance1, PromptComparison)


def test_generate_side_by_side_diff_identical(comparator):
    """Test side-by-side diff with identical texts."""
    text = "Line 1\nLine 2"
    diff = comparator.generate_side_by_side_diff(text, text)

    assert len(diff) == 2
    assert diff[0] == (" ", "Line 1", "Line 1")
    assert diff[1] == (" ", "Line 2", "Line 2")


def test_generate_side_by_side_diff_added(comparator):
    """Test side-by-side diff when lines are added."""
    text1 = "Line 1\nLine 3"
    text2 = "Line 1\nLine 2\nLine 3"
    diff = comparator.generate_side_by_side_diff(text1, text2)

    assert len(diff) == 3
    assert diff[0] == (" ", "Line 1", "Line 1")
    assert diff[1] == ("+", "", "Line 2")
    assert diff[2] == (" ", "Line 3", "Line 3")


def test_generate_side_by_side_diff_removed(comparator):
    """Test side-by-side diff when lines are removed."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine 3"
    diff = comparator.generate_side_by_side_diff(text1, text2)

    assert len(diff) == 3
    assert diff[0] == (" ", "Line 1", "Line 1")
    assert diff[1] == ("-", "Line 2", "")
    assert diff[2] == (" ", "Line 3", "Line 3")


def test_generate_side_by_side_diff_changed(comparator):
    """Test side-by-side diff when lines are replaced."""
    text1 = "Line 1\nLine 2\nLine 3"
    text2 = "Line 1\nLine TWO\nLine 3"
    diff = comparator.generate_side_by_side_diff(text1, text2)

    assert len(diff) == 3
    assert diff[0] == (" ", "Line 1", "Line 1")
    assert diff[1] == ("~", "Line 2", "Line TWO")
    assert diff[2] == (" ", "Line 3", "Line 3")


def test_generate_side_by_side_diff_changed_unequal(comparator):
    """Test side-by-side diff when unequal number of lines are replaced."""
    text1 = "Line 1\nLine 2\nLine 3\nLine 4"
    text2 = "Line 1\nLine TWO and THREE\nLine 4"
    diff = comparator.generate_side_by_side_diff(text1, text2)

    # Lines 2 and 3 are replaced by "Line TWO and THREE"
    # Result should show 2 changed lines to match the max length of the replace operation
    assert diff[0] == (" ", "Line 1", "Line 1")
    # First line of the replace
    assert diff[1] == ("~", "Line 2", "Line TWO and THREE")
    # Second line of the replace (from text1, but text2 has no corresponding line)
    assert diff[2] == ("~", "Line 3", "")
    assert diff[3] == (" ", "Line 4", "Line 4")


def test_generate_side_by_side_diff_empty(comparator):
    """Test side-by-side diff with empty texts."""
    diff_both_empty = comparator.generate_side_by_side_diff("", "")
    assert len(diff_both_empty) == 0

    diff_one_empty = comparator.generate_side_by_side_diff("Line 1", "")
    assert len(diff_one_empty) == 1
    assert diff_one_empty[0] == ("-", "Line 1", "")

    diff_other_empty = comparator.generate_side_by_side_diff("", "Line 1")
    assert len(diff_other_empty) == 1
    assert diff_other_empty[0] == ("+", "", "Line 1")


class MockEntry:
    def __init__(self, prompt_id, prompt_text):
        self.id = prompt_id
        self.prompt_id = prompt_id
        self.prompt_text = prompt_text


def test_get_prompt_text():
    from unittest.mock import MagicMock

    comp = PromptComparison.__new__(PromptComparison)
    comp.history = MagicMock()
    comp.favorites = MagicMock()

    # Setup mock data
    history_entry = MockEntry("hist1", "history text content")
    favorite_entry = MockEntry("fav1", "favorite text content")

    comp.history.get_by_id.side_effect = lambda x: history_entry if x == "hist1" else None
    comp.favorites.get_by_id.side_effect = lambda x: favorite_entry if x == "fav1" else None
    comp.favorites.entries = [favorite_entry]

    # Test auto source - favorites first
    success, text, src = comp.get_prompt_text("fav1")
    assert success is True
    assert text == "favorite text content"
    assert src == "favorites"

    # Test auto source - history fallback
    success, text, src = comp.get_prompt_text("hist1")
    assert success is True
    assert text == "history text content"
    assert src == "history"

    # Test explicit favorites source
    success, text, src = comp.get_prompt_text("fav1", source="favorites")
    assert success is True
    assert text == "favorite text content"

    # Test explicit history source
    success, text, src = comp.get_prompt_text("hist1", source="history")
    assert success is True
    assert text == "history text content"

    # Test not found
    success, text, src = comp.get_prompt_text("nonexistent")
    assert success is False
    assert "not found" in text
    assert src == "none"


def test_display_comparison(capsys):
    from unittest.mock import MagicMock

    comp = PromptComparison.__new__(PromptComparison)
    comp.history = MagicMock()
    comp.favorites = MagicMock()
    comp.console = MagicMock()

    # Setup mock data: only id1 and id2 exist
    entry1 = MockEntry("id1", "hello\nworld")
    entry2 = MockEntry("id2", "hello\nthere\nworld")

    comp.favorites.get_by_id.side_effect = (
        lambda x: entry1 if x == "id1" else entry2 if x == "id2" else None
    )
    comp.favorites.entries = [entry1, entry2]

    comp.history.get_by_id.return_value = None  # Ensure history queries default to None

    # Test side-by-side display success
    res = comp.display_comparison("id1", "id2", show_side_by_side=True)
    assert res is True

    # Test unified display success
    res2 = comp.display_comparison("id1", "id2", show_side_by_side=False)
    assert res2 is True

    # Test failure on first id
    res_fail1 = comp.display_comparison("nonexistent", "id2")
    assert res_fail1 is False

    # Test failure on second id
    res_fail2 = comp.display_comparison("id1", "nonexistent")
    assert res_fail2 is False
