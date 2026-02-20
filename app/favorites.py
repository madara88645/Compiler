class FavoritesManager:
    def __init__(self):
        self.entries = []

    def get_by_id(self, item_id):
        return None


_mgr = None


def get_favorites_manager():
    global _mgr
    if _mgr is None:
        _mgr = FavoritesManager()
    return _mgr
