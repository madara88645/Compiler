import pytest
from pydantic import ValidationError

from api.routes.generators import GitHubRepoContextPayload


def test_github_repo_context_payload_valid_lists():
    # Should not raise any validation error
    payload = GitHubRepoContextPayload(
        normalized_repo_url="https://github.com/foo/bar",
        repo_full_name="foo/bar",
        summary="A summary",
        highlights=["short item 1", "short item 2"],
        files_used=["file1.py"],
        detected_stack=["python", "fastapi"],
    )
    assert payload.highlights == ["short item 1", "short item 2"]
    assert payload.files_used == ["file1.py"]
    assert payload.detected_stack == ["python", "fastapi"]


def test_github_repo_context_payload_empty_lists():
    # Should not raise any validation error
    payload = GitHubRepoContextPayload(
        normalized_repo_url="https://github.com/foo/bar",
        repo_full_name="foo/bar",
        summary="A summary",
        highlights=[],
        files_used=[],
        detected_stack=[],
    )
    assert payload.highlights == []
    assert payload.files_used == []
    assert payload.detected_stack == []


@pytest.mark.parametrize("field_name", ["highlights", "files_used", "detected_stack"])
def test_github_repo_context_payload_exceeds_max_length(field_name):
    # Create valid base data
    data = {
        "normalized_repo_url": "https://github.com/foo/bar",
        "repo_full_name": "foo/bar",
        "summary": "A summary",
    }

    # Add the invalid field with an item that exceeds 1024 characters
    data[field_name] = ["a" * 1025]

    with pytest.raises(ValidationError) as exc_info:
        GitHubRepoContextPayload(**data)

    assert "Item in list exceeds maximum length of 1024 characters" in str(exc_info.value)
