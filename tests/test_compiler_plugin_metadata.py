from app.compiler import _ensure_plugin_metadata


def test_ensure_plugin_metadata_creates_default_when_missing():
    md = {}
    entry = _ensure_plugin_metadata(md)
    assert entry == {"applied": [], "errors": []}
    assert md["plugins"] is entry


def test_ensure_plugin_metadata_creates_default_when_not_a_dict():
    md = {"plugins": "not-a-dict"}
    entry = _ensure_plugin_metadata(md)
    assert entry == {"applied": [], "errors": []}
    assert md["plugins"] is entry


def test_ensure_plugin_metadata_fills_missing_keys_on_existing_dict():
    existing = {"applied": ["safety"]}
    md = {"plugins": existing}
    entry = _ensure_plugin_metadata(md)
    assert entry is existing
    assert entry == {"applied": ["safety"], "errors": []}


def test_ensure_plugin_metadata_preserves_existing_values():
    existing = {"applied": ["safety"], "errors": ["boom"]}
    md = {"plugins": existing}
    entry = _ensure_plugin_metadata(md)
    assert entry == {"applied": ["safety"], "errors": ["boom"]}
