from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.github_repo_context import (
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
