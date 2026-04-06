import pytest

from compile_settings import (
    build_compile_body,
    build_compile_headers,
    resolve_api_key,
    resolve_compile_post_url,
    resolve_prompt_mode,
)


def test_resolve_compile_post_url_prefers_full_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPTC_API_URL", raising=False)
    monkeypatch.delenv("PROMPTC_BACKEND_URL", raising=False)
    assert resolve_compile_post_url() == "http://localhost:8000/compile"

    monkeypatch.setenv("PROMPTC_API_URL", "https://api.example/compile/")
    assert resolve_compile_post_url() == "https://api.example/compile"


def test_resolve_compile_post_url_backend_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPTC_API_URL", raising=False)
    monkeypatch.setenv("PROMPTC_BACKEND_URL", "https://railway.app/promptc")
    assert resolve_compile_post_url() == "https://railway.app/promptc/compile"


def test_resolve_prompt_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPTC_PROMPT_MODE", raising=False)
    assert resolve_prompt_mode() == "conservative"

    monkeypatch.setenv("PROMPTC_PROMPT_MODE", "default")
    assert resolve_prompt_mode() == "default"

    monkeypatch.setenv("PROMPTC_PROMPT_MODE", "bogus")
    assert resolve_prompt_mode() == "conservative"


def test_build_headers_and_body_match_extension_contract() -> None:
    headers = build_compile_headers("default", "secret")
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Prompt-Mode"] == "default"
    assert headers["x-api-key"] == "secret"

    assert "x-api-key" not in build_compile_headers("conservative", None)

    body = build_compile_body("hello", "conservative")
    assert body == {
        "text": "hello",
        "diagnostics": False,
        "v2": True,
        "render_v2_prompts": True,
        "mode": "conservative",
    }


def test_resolve_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPTC_API_KEY", raising=False)
    assert resolve_api_key() is None

    monkeypatch.setenv("PROMPTC_API_KEY", "  k  ")
    assert resolve_api_key() == "k"
