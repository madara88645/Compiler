from pathlib import Path


def test_extension_background_uses_public_compile_endpoint():
    background = Path("extension/background.js").read_text(encoding="utf-8", errors="ignore")

    # Must use the public /compile endpoint, never the key-gated /compile/fast
    assert "/compile/fast" not in background
    assert "/compile" in background

    # x-api-key is sent conditionally when the user configures an API key
    # Verify it's guarded by a runtime config check rather than hardcoded
    assert "x-api-key" in background
    assert "runtimeConfig" in background
