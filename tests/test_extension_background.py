from pathlib import Path


def test_extension_background_uses_public_compile_endpoint_without_api_key():
    background = Path("extension/background.js").read_text(encoding="utf-8", errors="ignore")

    assert "/compile/fast" not in background
    assert "x-api-key" not in background
    assert "apiKey:" not in background
    assert "/compile" in background
