from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.github_repo_context import (
    GitHubRepoAnalysisError,
    InvalidGitHubRepoUrl,
    _build_summary_compact,
    analyze_public_github_repo,
    normalize_public_github_repo_url,
    reset_repo_cache_for_tests,
)


client = TestClient(app)


def test_normalize_public_github_repo_url_accepts_root_url():
    normalized = normalize_public_github_repo_url("https://github.com/openai/openai-python/")

    assert normalized == "https://github.com/openai/openai-python"


@pytest.mark.parametrize(
    "repo_url",
    [
        "https://github.com/openai/openai-python.git",
        "https://github.com/openai/openai-python/tree/main",
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


def test_analyze_public_github_repo_uses_in_memory_cache(monkeypatch):
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
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path):
            call_log.append(path)
            if path.endswith("/repos/openai/openai-python"):
                return FakeResponse(repo_meta)
            if path.endswith("/repos/openai/openai-python/contents"):
                return FakeResponse(root_entries)
            if path == "rd":
                return FakeResponse(None, text="# OpenAI Python\n\nOfficial SDK.")
            if path == "py":
                return FakeResponse(None, text="[project]\nname='openai'\n")
            return FakeResponse([])

    monkeypatch.setattr("app.github_repo_context.httpx.Client", FakeClient)

    first = analyze_public_github_repo("https://github.com/openai/openai-python")
    second = analyze_public_github_repo("https://github.com/openai/openai-python")

    assert first == second
    assert "summary_compact" in first and first["summary_compact"]
    assert (
        call_log.count("/repos/openai/openai-python") == 1
    ), f"expected GitHub API to be hit once, got call log: {call_log}"

    reset_repo_cache_for_tests()


def test_analyze_public_github_repo_forwards_promptc_github_token(monkeypatch):
    reset_repo_cache_for_tests()
    monkeypatch.setenv("PROMPTC_GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    captured_headers: dict[str, str] = {}

    class HeaderCapturingClient:
        def __init__(self, *args, **kwargs):
            captured_headers.update(dict(kwargs.get("headers") or {}))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path):
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
            captured_headers.update(dict(kwargs.get("headers") or {}))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path):
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
    assert response.json() == {**mock_payload, "summary_compact": None}
    mock_analyze.assert_called_once_with("https://github.com/openai/openai-python")
