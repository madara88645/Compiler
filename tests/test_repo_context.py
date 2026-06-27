from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.github_repo_context import (
    GitHubRepoAnalysisError,
    InvalidGitHubRepoUrl,
    _build_summary,
    _build_summary_compact,
    _detect_stack,
    analyze_public_github_repo,
    normalize_public_github_repo_url,
    reset_repo_cache_for_tests,
)


client = TestClient(app)


def test_normalize_public_github_repo_url_accepts_root_url():
    normalized, requested_ref, requested_subdir = normalize_public_github_repo_url(
        "https://github.com/openai/openai-python/"
    )

    assert normalized == "https://github.com/openai/openai-python"
    assert requested_ref is None
    assert requested_subdir is None


@pytest.mark.parametrize(
    ("repo_url", "expected_root", "expected_ref", "expected_subdir"),
    [
        (
            "https://github.com/openai/openai-python/tree/main",
            "https://github.com/openai/openai-python",
            "main",
            None,
        ),
        (
            "https://github.com/vercel/next.js/tree/canary/packages/next",
            "https://github.com/vercel/next.js",
            "canary",
            "packages/next",
        ),
    ],
)
def test_normalize_public_github_repo_url_accepts_tree_variants(
    repo_url: str,
    expected_root: str,
    expected_ref: str,
    expected_subdir: str | None,
):
    normalized, requested_ref, requested_subdir = normalize_public_github_repo_url(repo_url)
    assert normalized == expected_root
    assert requested_ref == expected_ref
    assert requested_subdir == expected_subdir


@pytest.mark.parametrize(
    "repo_url",
    [
        "https://github.com/openai/openai-python.git",
        "https://github.com/openai/openai-python/blob/main/README.md",
        "https://github.com/openai/openai-python?tab=readme-ov-file",
        "https://github.com/openai/openai-python#readme",
        "https://github.com/openai/openai-python/issues",
    ],
)
def test_normalize_public_github_repo_url_rejects_non_root_variants(repo_url: str):
    with pytest.raises(InvalidGitHubRepoUrl):
        normalize_public_github_repo_url(repo_url)


def test_build_summary_compact_truncates_to_budget():
    repo_meta = {
        "full_name": "openai/openai-python",
        "description": "Official Python SDK for the OpenAI API.",
    }
    compact = _build_summary_compact(
        repo_meta=repo_meta,
        detected_stack=["Python", "httpx", "pydantic"],
        top_level_dirs=["src", "tests"],
    )
    assert compact.startswith("openai/openai-python:")
    assert "Python" in compact
    assert len(compact) <= 280


def test_build_summary_compact_handles_missing_metadata():
    compact = _build_summary_compact(
        repo_meta={},
        detected_stack=[],
        top_level_dirs=[],
    )
    assert "no detected stack" in compact
    assert "single-surface" in compact


def test_build_summary_truncates_long_readme_signal():
    summary = _build_summary(
        repo_meta={
            "full_name": "openai/openai-python",
            "description": "Official Python SDK for the OpenAI API.",
        },
        detected_stack=["Python", "FastAPI", "httpx"],
        top_level_dirs=["web", "api", "tests"],
        files_used=["README.md", "pyproject.toml"],
        manifest_paths=["pyproject.toml"],
        readme_text=("README " * 600).strip(),
    )

    assert len(summary) <= 1200
    assert "README signal:" in summary
    assert "README README README" in summary
    assert "REA..." in summary


def test_detect_stack_combines_manifest_and_language_signals():
    detected = _detect_stack(
        {"language": "TypeScript"},
        {
            "package.json": (
                '{"dependencies":{"next":"15.0.0","react":"19.0.0"},'
                '"devDependencies":{"typescript":"5.0.0"}}'
            ),
            "pyproject.toml": "[project]\ndependencies=['fastapi','httpx']\n",
        },
    )

    assert detected == ["TypeScript", "Node.js", "Next.js", "React", "Python", "FastAPI"]


def test_analyze_public_github_repo_uses_ref_and_subdir_cache_key(monkeypatch):
    reset_repo_cache_for_tests()

    repo_meta = {
        "full_name": "openai/openai-python",
        "description": "Python SDK for OpenAI.",
        "default_branch": "main",
        "language": "Python",
    }
    root_entries = [
        {"name": "README.md", "path": "README.md", "type": "file", "download_url": "rd"},
        {"name": "pyproject.toml", "path": "pyproject.toml", "type": "file", "download_url": "py"},
    ]

    call_log: list[str] = []

    class FakeResponse:
        def __init__(self, payload, *, text=""):
            self._payload = payload
            self.text = text
            self.status_code = 200

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            call_log.append(path)
            if path.endswith("/repos/openai/openai-python"):
                return FakeResponse(repo_meta)
            if path in (
                "/repos/openai/openai-python/contents?ref=main",
                "/repos/openai/openai-python/contents?ref=v4",
            ):
                return FakeResponse(root_entries)
            if path == "rd":
                return FakeResponse(None, text="# OpenAI Python\n\nOfficial SDK.")
            if path == "py":
                return FakeResponse(None, text="[project]\nname='openai'\n")
            return FakeResponse([])

    monkeypatch.setattr("app.github_repo_context.httpx.Client", FakeClient)

    first = analyze_public_github_repo("https://github.com/openai/openai-python/tree/main")
    second = analyze_public_github_repo("https://github.com/openai/openai-python/tree/main")
    third = analyze_public_github_repo("https://github.com/openai/openai-python/tree/v4")

    assert first == second
    assert third["requested_ref"] == "v4"
    assert "summary_compact" in first and first["summary_compact"]
    assert (
        call_log.count("/repos/openai/openai-python") == 2
    ), f"expected GitHub API to be hit twice for two refs, got call log: {call_log}"
    assert call_log.count("/repos/openai/openai-python/contents?ref=main") == 1
    assert call_log.count("/repos/openai/openai-python/contents?ref=v4") == 1

    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_uses_in_memory_cache_for_root_url(monkeypatch):
    reset_repo_cache_for_tests()

    repo_meta = {
        "full_name": "openai/openai-python",
        "description": "Python SDK for OpenAI.",
        "default_branch": "main",
        "language": "Python",
    }
    root_entries = [
        {"name": "README.md", "path": "README.md", "type": "file", "download_url": "rd"},
    ]
    call_log: list[str] = []

    class FakeResponse:
        def __init__(self, payload, *, text=""):
            self._payload = payload
            self.text = text
            self.status_code = 200

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            call_log.append(path)
            if path.endswith("/repos/openai/openai-python"):
                return FakeResponse(repo_meta)
            if path == "/repos/openai/openai-python/contents":
                return FakeResponse(root_entries)
            if path == "rd":
                return FakeResponse(None, text="# OpenAI Python\n\nOfficial SDK.")
            return FakeResponse([])

    monkeypatch.setattr("app.github_repo_context.httpx.Client", FakeClient)

    first = analyze_public_github_repo("https://github.com/openai/openai-python")
    second = analyze_public_github_repo("https://github.com/openai/openai-python")

    assert first == second
    assert first["requested_ref"] is None
    assert first["requested_subdir"] is None
    assert (
        call_log.count("/repos/openai/openai-python") == 1
    ), f"expected GitHub API to be hit once for root URL, got call log: {call_log}"

    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_forwards_ref_to_contents_api(monkeypatch):
    reset_repo_cache_for_tests()
    call_log: list[str] = []

    repo_meta = {
        "full_name": "openai/openai-python",
        "description": "Python SDK for OpenAI.",
        "default_branch": "main",
        "language": "Python",
    }
    root_entries = [
        {"name": "README.md", "path": "README.md", "type": "file", "download_url": "rd"}
    ]

    class FakeResponse:
        def __init__(self, payload, *, text=""):
            self._payload = payload
            self.text = text
            self.status_code = 200

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            call_log.append(path)
            if path.endswith("/repos/openai/openai-python"):
                return FakeResponse(repo_meta)
            if path == "/repos/openai/openai-python/contents?ref=my-branch":
                return FakeResponse(root_entries)
            if path == "rd":
                return FakeResponse(None, text="# README")
            return FakeResponse([])

    monkeypatch.setattr("app.github_repo_context.httpx.Client", FakeClient)
    payload = analyze_public_github_repo("https://github.com/openai/openai-python/tree/my-branch")
    assert payload["requested_ref"] == "my-branch"
    assert "/repos/openai/openai-python/contents?ref=my-branch" in call_log
    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_walks_requested_subdir(monkeypatch):
    reset_repo_cache_for_tests()
    call_log: list[str] = []

    repo_meta = {
        "full_name": "vercel/next.js",
        "description": "Next.js repo",
        "default_branch": "canary",
        "language": "TypeScript",
    }
    subdir_entries = [
        {
            "name": "README.md",
            "path": "packages/next/README.md",
            "type": "file",
            "download_url": "rd",
        }
    ]

    class FakeResponse:
        def __init__(self, payload, *, text=""):
            self._payload = payload
            self.text = text
            self.status_code = 200

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            call_log.append(path)
            if path.endswith("/repos/vercel/next.js"):
                return FakeResponse(repo_meta)
            if path == "/repos/vercel/next.js/contents/packages/next?ref=canary":
                return FakeResponse(subdir_entries)
            if path == "rd":
                return FakeResponse(None, text="# Next package")
            return FakeResponse([])

    monkeypatch.setattr("app.github_repo_context.httpx.Client", FakeClient)
    payload = analyze_public_github_repo(
        "https://github.com/vercel/next.js/tree/canary/packages/next"
    )
    assert payload["requested_ref"] == "canary"
    assert payload["requested_subdir"] == "packages/next"
    assert "/repos/vercel/next.js/contents/packages/next?ref=canary" in call_log
    assert "/repos/vercel/next.js/contents?ref=canary" not in call_log
    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_forwards_promptc_github_token(monkeypatch):
    reset_repo_cache_for_tests()
    monkeypatch.setenv("PROMPTC_GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    captured_headers: dict[str, str] = {}

    class HeaderCapturingClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            captured_headers.update(headers or {})
            raise httpx.HTTPError("stop after header capture")

    monkeypatch.setattr("app.github_repo_context.httpx.Client", HeaderCapturingClient)

    with pytest.raises(GitHubRepoAnalysisError):
        analyze_public_github_repo("https://github.com/openai/openai-python")

    assert captured_headers.get("Authorization") == "Bearer ghp_test_token"
    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_omits_authorization_when_no_token(monkeypatch):
    reset_repo_cache_for_tests()
    monkeypatch.delenv("PROMPTC_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    captured_headers: dict[str, str] = {}

    class HeaderCapturingClient:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path, headers=None, **kwargs):
            captured_headers.update(headers or {})
            raise httpx.HTTPError("stop after header capture")

    monkeypatch.setattr("app.github_repo_context.httpx.Client", HeaderCapturingClient)

    with pytest.raises(GitHubRepoAnalysisError):
        analyze_public_github_repo("https://github.com/openai/openai-python")

    assert "Authorization" not in captured_headers
    reset_repo_cache_for_tests()


def _enable_promptc_api_log_capture(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="promptc.api")
    logger = logging.getLogger("promptc.api")
    previous_propagate = logger.propagate
    logger.propagate = True
    return previous_propagate


def _restore_promptc_api_log_capture(previous_propagate):
    import logging

    logging.getLogger("promptc.api").propagate = previous_propagate


def test_repo_context_endpoint_emits_ok_telemetry(caplog):
    mock_payload = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repo with README-led overview and manifest-derived stack.",
        "highlights": ["Python package", "README present"],
        "files_used": ["README.md", "pyproject.toml"],
        "detected_stack": ["Python", "httpx"],
    }

    previous_propagate = _enable_promptc_api_log_capture(caplog)
    try:
        with patch("api.routes.generators.analyze_public_github_repo", return_value=mock_payload):
            response = client.post(
                "/repo-context/github",
                json={"repo_url": "https://github.com/openai/openai-python"},
            )
    finally:
        _restore_promptc_api_log_capture(previous_propagate)

    assert response.status_code == 200

    analyze_records = [r for r in caplog.records if getattr(r, "event", None) == "repo_analyze"]
    assert analyze_records, "expected at least one repo_analyze structured log record"
    record = analyze_records[-1]
    assert record.outcome == "ok"
    assert record.repo_full_name == "openai/openai-python"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, (int, float))


def test_repo_context_endpoint_emits_invalid_url_telemetry(caplog):
    previous_propagate = _enable_promptc_api_log_capture(caplog)
    try:
        response = client.post(
            "/repo-context/github",
            json={"repo_url": "https://gitlab.com/openai/openai-python"},
        )
    finally:
        _restore_promptc_api_log_capture(previous_propagate)

    assert response.status_code == 400

    analyze_records = [r for r in caplog.records if getattr(r, "event", None) == "repo_analyze"]
    assert analyze_records, "expected an invalid_url telemetry record"
    record = analyze_records[-1]
    assert record.outcome == "invalid_url"
    assert record.status_code == 400


def test_repo_context_endpoint_emits_not_found_telemetry(caplog):
    previous_propagate = _enable_promptc_api_log_capture(caplog)
    try:
        with patch(
            "api.routes.generators.analyze_public_github_repo",
            side_effect=GitHubRepoAnalysisError("Repository not found.", status_code=404),
        ):
            response = client.post(
                "/repo-context/github",
                json={"repo_url": "https://github.com/openai/missing-repo"},
            )
    finally:
        _restore_promptc_api_log_capture(previous_propagate)

    assert response.status_code == 404

    analyze_records = [r for r in caplog.records if getattr(r, "event", None) == "repo_analyze"]
    assert analyze_records, "expected a not_found telemetry record"
    record = analyze_records[-1]
    assert record.outcome == "not_found"
    assert record.repo_full_name == "openai/missing-repo"
    assert record.status_code == 404


def test_repo_context_endpoint_emits_upstream_error_telemetry(caplog):
    previous_propagate = _enable_promptc_api_log_capture(caplog)
    try:
        with patch(
            "api.routes.generators.analyze_public_github_repo",
            side_effect=GitHubRepoAnalysisError(
                "GitHub repository analysis failed.", status_code=502
            ),
        ):
            response = client.post(
                "/repo-context/github",
                json={"repo_url": "https://github.com/openai/openai-python"},
            )
    finally:
        _restore_promptc_api_log_capture(previous_propagate)

    assert response.status_code == 502

    analyze_records = [r for r in caplog.records if getattr(r, "event", None) == "repo_analyze"]
    assert analyze_records, "expected an upstream_error telemetry record"
    record = analyze_records[-1]
    assert record.outcome == "upstream_error"
    assert record.repo_full_name == "openai/openai-python"
    assert record.status_code == 502


def test_repo_context_endpoint_returns_analyzed_repo_summary():
    mock_payload = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repo with README-led overview and manifest-derived stack.",
        "highlights": ["Python package", "README present"],
        "files_used": ["README.md", "pyproject.toml"],
        "detected_stack": ["Python", "httpx"],
    }

    with patch(
        "api.routes.generators.analyze_public_github_repo", return_value=mock_payload
    ) as mock_analyze:
        response = client.post(
            "/repo-context/github",
            json={"repo_url": "https://github.com/openai/openai-python"},
        )

    assert response.status_code == 200
    # Response model adds summary_compact (defaults to None when analyzer omits it).
    assert response.json() == {
        **mock_payload,
        "summary_compact": None,
        "requested_ref": None,
        "requested_subdir": None,
    }
    mock_analyze.assert_called_once_with("https://github.com/openai/openai-python")


def test_analyze_public_github_repo_authorization_leakage_regression(monkeypatch):
    reset_repo_cache_for_tests()

    # 1. Aşama: Token varken istek yapıyoruz
    monkeypatch.setenv("PROMPTC_GITHUB_TOKEN", "ghp_regression_token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    captured_client_headers = []
    captured_request_headers = []

    def mock_get(self_client, path, *args, **kwargs):
        captured_client_headers.append(dict(self_client.headers))
        captured_request_headers.append(dict(kwargs.get("headers") or {}))
        raise httpx.HTTPError("stop after first capture")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(GitHubRepoAnalysisError):
        analyze_public_github_repo("https://github.com/openai/openai-python")

    assert len(captured_client_headers) == 1
    # Mevcut kodda (sızdıran durumda) global client headers'a token eklenir.
    # Ancak düzeltilmiş kodda client.headers içinde Authorization olmamalı, request headers içinde olmalı.

    # 2. Aşama: Token siliniyor ve aynı client ile tekrar istek yapılıyor
    monkeypatch.delenv("PROMPTC_GITHUB_TOKEN", raising=False)

    # Cache'i sıfırlayalım ki API isteği tekrar atılsın, ancak global client sıfırlanmasın
    import app.github_repo_context

    if app.github_repo_context._REPO_CACHE is not None:
        app.github_repo_context._REPO_CACHE.clear()

    with pytest.raises(GitHubRepoAnalysisError):
        analyze_public_github_repo("https://github.com/openai/openai-python")

    print("\n--- DEBUG START ---")
    print("captured_client_headers:", captured_client_headers)
    print("captured_request_headers:", captured_request_headers)
    print("--- DEBUG END ---\n")

    assert len(captured_client_headers) == 2

    # Case-insensitive key checks for authorization header
    has_auth_client = any(k.lower() == "authorization" for k in captured_client_headers[1])
    has_auth_request = any(k.lower() == "authorization" for k in captured_request_headers[1])

    assert not has_auth_client, f"Leakage detected: Authorization persisted in global client headers! Headers: {captured_client_headers[1]}"
    assert not has_auth_request, f"Leakage detected: Authorization sent in second request! Headers: {captured_request_headers[1]}"


def test_close_github_http_client():
    from app.github_repo_context import get_github_http_client, close_github_http_client
    import app.github_repo_context

    client = get_github_http_client()
    assert client is not None
    assert app.github_repo_context._GITHUB_HTTP_CLIENT is not None

    close_github_http_client()
    assert app.github_repo_context._GITHUB_HTTP_CLIENT is None


def test_resolve_repo_cache_ttl_variants(monkeypatch):
    from app.github_repo_context import _resolve_repo_cache_ttl

    # 1. Negative TTL
    monkeypatch.setenv("PROMPTC_REPO_CONTEXT_CACHE_TTL", "-5")
    assert _resolve_repo_cache_ttl() == 0

    # 2. Empty TTL
    monkeypatch.setenv("PROMPTC_REPO_CONTEXT_CACHE_TTL", "   ")
    assert _resolve_repo_cache_ttl() == 600

    # 3. Invalid TTL
    monkeypatch.setenv("PROMPTC_REPO_CONTEXT_CACHE_TTL", "invalid-int")
    assert _resolve_repo_cache_ttl() == 600


def test_normalize_public_github_repo_url_edge_cases():
    from app.github_repo_context import normalize_public_github_repo_url

    # Empty URL
    with pytest.raises(InvalidGitHubRepoUrl, match="URL is required"):
        normalize_public_github_repo_url("")

    # Invalid scheme / host
    with pytest.raises(InvalidGitHubRepoUrl, match="Only public https://github.com"):
        normalize_public_github_repo_url("http://github.com/a/b")
    with pytest.raises(InvalidGitHubRepoUrl, match="Only public https://github.com"):
        normalize_public_github_repo_url("https://gitlab.com/a/b")

    # Query or fragment
    with pytest.raises(InvalidGitHubRepoUrl, match="Only root repository URLs are supported"):
        normalize_public_github_repo_url("https://github.com/a/b?ref=main")

    # Too few segments
    with pytest.raises(InvalidGitHubRepoUrl, match="Only root repository URLs are supported"):
        normalize_public_github_repo_url("https://github.com/a")

    # Invalid characters in owner/repo
    with pytest.raises(InvalidGitHubRepoUrl, match="contains unsupported characters"):
        normalize_public_github_repo_url("https://github.com/owner$/repo")

    # Tree segment but empty ref
    with pytest.raises(InvalidGitHubRepoUrl, match="Only root repository URLs are supported"):
        normalize_public_github_repo_url("https://github.com/a/b/tree/")

    # Invalid segment structure (not tree)
    with pytest.raises(InvalidGitHubRepoUrl, match="Only root repository URLs are supported"):
        normalize_public_github_repo_url("https://github.com/a/b/blob")


def test_analyze_public_github_repo_no_cache(monkeypatch):
    import app.github_repo_context
    from app.github_repo_context import analyze_public_github_repo

    # Temporarily set _REPO_CACHE to None
    monkeypatch.setattr(app.github_repo_context, "_REPO_CACHE", None)

    # Mock fetch payload
    mock_payload = {"normalized_repo_url": "url"}
    with patch(
        "app.github_repo_context._fetch_public_github_repo_payload", return_value=mock_payload
    ):
        res = analyze_public_github_repo("https://github.com/owner/repo")
        assert res == mock_payload


def test_resolve_github_token_variants(monkeypatch):
    from app.github_repo_context import _resolve_github_token

    # 1. GITHUB_TOKEN present
    monkeypatch.setenv("GITHUB_TOKEN", "token1")
    monkeypatch.delenv("PROMPTC_GITHUB_TOKEN", raising=False)
    assert _resolve_github_token() == "token1"

    # 2. Both empty/whitespace
    monkeypatch.setenv("GITHUB_TOKEN", "  ")
    assert _resolve_github_token() is None


def test_get_json_exceptions():
    from app.github_repo_context import _get_json
    from unittest.mock import MagicMock

    mock_client = MagicMock(spec=httpx.Client)

    # 1. Status 500 error
    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    mock_client.get.return_value = mock_response_500
    mock_response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Err", request=MagicMock(), response=mock_response_500
    )

    with pytest.raises(GitHubRepoAnalysisError, match="repository analysis failed"):
        _get_json(mock_client, "/path")

    # 2. HTTPError
    mock_client.get.side_effect = httpx.HTTPError("Network failure")
    with pytest.raises(GitHubRepoAnalysisError, match="repository analysis failed"):
        _get_json(mock_client, "/path")


def test_read_text_file_exceptions():
    from app.github_repo_context import _read_text_file
    from unittest.mock import MagicMock

    mock_client = MagicMock(spec=httpx.Client)

    # 1. Missing download url
    assert _read_text_file(mock_client, {}) == ""

    # 2. HTTPError during download
    mock_client.get.side_effect = httpx.HTTPError("Err")
    assert _read_text_file(mock_client, {"download_url": "url"}) == ""


def test_find_entry_not_found():
    from app.github_repo_context import _find_entry

    assert _find_entry([], "target") is None


def test_find_readme_not_found():
    from app.github_repo_context import _find_readme

    assert _find_readme([{"name": "not-readme", "type": "file"}]) is None
    assert _find_readme([{"name": "readme.md", "type": "dir"}]) is None


def test_detect_stack_exceptions_and_frameworks():
    from app.github_repo_context import _detect_stack

    # 1. Missing language
    res1 = _detect_stack({}, {})
    assert res1 == []

    # 2. package.json invalid json syntax
    res2 = _detect_stack({"language": "JavaScript"}, {"package.json": "invalid-json"})
    assert "Node.js" in res2
    assert "React" not in res2

    # 3. All other stack frameworks (split into two groups to avoid MAX_STACK_ITEMS truncation)
    group1 = {
        "django_file": "django framework",
        "flask_file": "flask framework",
        "cargo.toml": "Rust cargo.toml",
    }
    res_group1 = _detect_stack({"language": "Python"}, group1)
    for framework in ["Django", "Flask", "Rust"]:
        assert framework in res_group1

    group2 = {
        "go.mod": "Go go.mod",
        "pom.xml": "Java pom.xml",
        "composer.json": "PHP composer.json",
        "gemfile": "Ruby gemfile",
    }
    res_group2 = _detect_stack({}, group2)
    for framework in ["Go", "Java", "PHP", "Ruby"]:
        assert framework in res_group2


def test_build_highlights_edge_cases():
    from app.github_repo_context import _build_highlights

    # Empty metadata/paths/files
    res = _build_highlights(
        repo_meta={},
        detected_stack=[],
        top_level_dirs=[],
        files_used=[],
        manifest_paths=[],
    )
    assert len(res) == 1
    assert "This repository" in res[0]


def test_build_summary_budget_exceeded():
    from app.github_repo_context import _build_summary

    long_readme = "readme " * 500
    res = _build_summary(
        repo_meta={"full_name": "owner/repo", "description": "desc " * 300},
        detected_stack=["Python"],
        top_level_dirs=["src"],
        files_used=["README.md"],
        manifest_paths=["pyproject.toml"],
        readme_text=long_readme,
    )
    assert len(res) <= 1200
    assert res.endswith("...")


def test_build_summary_compact_budget_exceeded():
    from app.github_repo_context import _build_summary_compact

    res = _build_summary_compact(
        repo_meta={"full_name": "owner/repo", "description": "description " * 100},
        detected_stack=["Python", "FastAPI"],
        top_level_dirs=["src"],
    )
    assert len(res) <= 280
    assert res.endswith("...")


def test_extract_readme_signal_empty():
    from app.github_repo_context import _extract_readme_signal

    res = _extract_readme_signal("")
    assert "README content was unavailable" in res
