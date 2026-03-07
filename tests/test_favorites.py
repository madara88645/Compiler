from app.favorites import FavoritesManager


def test_favorites_manager_get_by_id():
    manager = FavoritesManager()
    result = manager.get_by_id("test_id_123")
    assert result is None
