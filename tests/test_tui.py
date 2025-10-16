"""Tests for Terminal UI components."""

from app.search import SearchResult, SearchResultType


# Test SearchResultItem rendering without requiring full Textual app
def test_search_result_item_icons():
    """Test that correct icons are used for different result types."""
    from app.tui import SearchResultItem

    icons = {
        SearchResultType.HISTORY: "📝",
        SearchResultType.FAVORITE: "⭐",
        SearchResultType.TEMPLATE: "📄",
        SearchResultType.SNIPPET: "📋",
        SearchResultType.COLLECTION: "🗂️",
    }

    for result_type, expected_icon in icons.items():
        result = SearchResult(
            id="test-id",
            title="Test Title",
            content="Test content",
            result_type=result_type,
            score=85.5,
            metadata={},
        )
        item = SearchResultItem(result)
        rendered = item.render()

        # Check that the rendered text contains the expected icon
        assert expected_icon in rendered.plain


def test_search_result_item_score_formatting():
    """Test that scores are formatted correctly."""
    from app.tui import SearchResultItem

    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=92.7,
        metadata={},
    )
    item = SearchResultItem(result)
    rendered = item.render()

    # Score should be formatted as 5.1f (e.g., " 92.7")
    assert "92.7" in rendered.plain


def test_search_result_item_title_truncation():
    """Test that long titles are truncated."""
    from app.tui import SearchResultItem

    long_title = "A" * 100  # Very long title
    result = SearchResult(
        id="test-id",
        title=long_title,
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=50.0,
        metadata={},
    )
    item = SearchResultItem(result)
    rendered = item.render()

    # Title should be truncated to 50 characters
    plain_text = rendered.plain
    # Count actual title characters (excluding icon and score)
    assert len(plain_text) < len(long_title) + 20  # +20 for icon/score/spaces


def test_preview_pane_content_truncation():
    """Test that preview pane truncates long content."""
    from app.tui import PreviewPane

    long_content = "X" * 1000
    result = SearchResult(
        id="test-id",
        title="Test",
        content=long_content,
        result_type=SearchResultType.TEMPLATE,
        score=75.0,
        metadata={},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)

    # Content should be truncated to 500 chars with "..."
    rendered = pane.render()
    assert "..." in str(rendered)


def test_preview_pane_with_metadata():
    """Test preview pane displays metadata."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=80.0,
        metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    assert "key1" in rendered
    assert "value1" in rendered


def test_preview_pane_metadata_limit():
    """Test that preview pane shows only first 5 metadata items."""
    from app.tui import PreviewPane

    metadata = {f"key{i}": f"value{i}" for i in range(10)}
    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=80.0,
        metadata=metadata,
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    # Should show first 5 items
    assert "key0" in rendered
    assert "key4" in rendered
    # Should not show items beyond 5
    assert "key9" not in rendered


def test_preview_pane_no_metadata():
    """Test preview pane with no metadata."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=80.0,
        metadata=None,
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    # Should not crash, should show basic info
    assert "Test" in rendered
    assert "80" in rendered


def test_preview_pane_displays_result_type():
    """Test that preview pane shows result type."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.FAVORITE,
        score=90.0,
        metadata={},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    assert "favorite" in rendered.lower()


def test_preview_pane_displays_score():
    """Test that preview pane shows score."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="test-id",
        title="Test",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=87.5,
        metadata={},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    assert "87.5" in rendered


def test_preview_pane_displays_id():
    """Test that preview pane shows result ID."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="unique-test-id-123",
        title="Test",
        content="Content",
        result_type=SearchResultType.SNIPPET,
        score=70.0,
        metadata={},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    assert "unique-test-id-123" in rendered


def test_preview_pane_empty_content():
    """Test preview pane with empty content."""
    from app.tui import PreviewPane

    result = SearchResult(
        id="test-id",
        title="Test",
        content="",
        result_type=SearchResultType.TEMPLATE,
        score=60.0,
        metadata={},
    )

    pane = PreviewPane(id="test-pane")
    pane.update_preview(result)
    rendered = str(pane.render())

    # Should not crash with empty content
    assert "Test" in rendered
    assert "60" in rendered


def test_search_result_item_different_scores():
    """Test result items with various score values."""
    from app.tui import SearchResultItem

    scores = [0.0, 25.5, 50.0, 75.3, 99.9, 100.0]

    for score in scores:
        result = SearchResult(
            id=f"test-{score}",
            title="Test",
            content="Content",
            result_type=SearchResultType.TEMPLATE,
            score=score,
            metadata={},
        )
        item = SearchResultItem(result)
        rendered = item.render()

        # Score should be in the rendered text
        assert str(score) in rendered.plain


def test_search_result_item_with_special_characters():
    """Test result item with special characters in title."""
    from app.tui import SearchResultItem

    special_title = "Test <>&\"'[] Special"
    result = SearchResult(
        id="test-id",
        title=special_title,
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=80.0,
        metadata={},
    )
    item = SearchResultItem(result)
    rendered = item.render()

    # Should handle special characters
    assert "Test" in rendered.plain
    assert "Special" in rendered.plain


def test_search_result_item_empty_title():
    """Test result item with empty title."""
    from app.tui import SearchResultItem

    result = SearchResult(
        id="test-id",
        title="",
        content="Content",
        result_type=SearchResultType.TEMPLATE,
        score=50.0,
        metadata={},
    )
    item = SearchResultItem(result)
    rendered = item.render()

    # Should still render with score and icon
    assert "50.0" in rendered.plain
    assert "📄" in rendered.plain


def test_run_tui_function_exists():
    """Test that run_tui function is exported."""
    from app.tui import run_tui

    assert callable(run_tui)


def test_search_app_css_defined():
    """Test that SearchApp has CSS defined."""
    from app.tui import SearchApp

    assert hasattr(SearchApp, "CSS")
    assert isinstance(SearchApp.CSS, str)
    assert len(SearchApp.CSS) > 0


def test_search_app_bindings_defined():
    """Test that SearchApp has key bindings."""
    from app.tui import SearchApp

    assert hasattr(SearchApp, "BINDINGS")
    bindings = SearchApp.BINDINGS

    # Should have bindings for F1-F4 and Ctrl+C
    binding_keys = [b.key for b in bindings]
    assert "f1" in binding_keys
    assert "f2" in binding_keys
    assert "f3" in binding_keys
    assert "f4" in binding_keys
    assert "ctrl+c" in binding_keys
