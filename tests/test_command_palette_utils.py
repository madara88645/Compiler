from app.command_palette import compute_stale_favorites


def test_compute_stale_favorites_orders_and_dedupes():
    favorites = ["a", "b", "a", "c", "d", "c"]
    valid = {"b", "d"}
    assert compute_stale_favorites(favorites, valid) == ["a", "c"]


def test_compute_stale_favorites_strips_and_filters_empty():
    favorites = ["  a  ", "", "  ", None]
    valid = {"a"}
    assert compute_stale_favorites(favorites, valid) == []


def test_compute_stale_favorites_all_stale_when_no_valids():
    favorites = ["x", "y"]
    valid = set()
    assert compute_stale_favorites(favorites, valid) == ["x", "y"]


def test_compute_stale_favorites_handles_iterables():
    favorites = (cid for cid in ["keep", "drop"])
    valid = ["keep"]
    assert compute_stale_favorites(favorites, valid) == ["drop"]
