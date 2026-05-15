from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.github_repo_context import InvalidGitHubRepoUrl, normalize_public_github_repo_url


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
    assert response.json() == mock_payload
    mock_analyze.assert_called_once_with("https://github.com/openai/openai-python")
