from app.favorites import FavoritesManager, get_favorites_manager


def test_get_favorites_manager_singleton():
    """Test that get_favorites_manager returns the same singleton instance."""
    manager1 = get_favorites_manager()
    manager2 = get_favorites_manager()

    assert manager1 is not None
    assert isinstance(manager1, FavoritesManager)
    assert manager1 is manager2


def test_favorites_manager_get_by_id():
    manager = FavoritesManager()
    result = manager.get_by_id("test_id_123")
    assert result is None
