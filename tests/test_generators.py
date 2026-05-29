import pytest
from pydantic import ValidationError

from api.routes.generators import GitHubRepoContextPayload


def test_validate_list_items_length_valid():
    # Test with valid strings (short and exactly 1024 characters)
    payload = GitHubRepoContextPayload(
        normalized_repo_url="https://github.com/foo/bar",
        repo_full_name="foo/bar",
        summary="A summary",
        highlights=["short string", "a" * 1024],
        files_used=["another string"],
        detected_stack=[]
    )
    assert len(payload.highlights) == 2
    assert payload.highlights[0] == "short string"
    assert payload.highlights[1] == "a" * 1024
    assert payload.files_used == ["another string"]
    assert payload.detected_stack == []


def test_validate_list_items_length_empty():
    # Test with empty lists (which are valid)
    payload = GitHubRepoContextPayload(
        normalized_repo_url="https://github.com/foo/bar",
        repo_full_name="foo/bar",
        summary="A summary",
        highlights=[],
        files_used=[],
        detected_stack=[]
    )
    assert payload.highlights == []
    assert payload.files_used == []
    assert payload.detected_stack == []


def test_validate_list_items_length_exceeds():
    # Test with string exceeding 1024 characters
    with pytest.raises(ValidationError) as exc_info:
        GitHubRepoContextPayload(
            normalized_repo_url="https://github.com/foo/bar",
            repo_full_name="foo/bar",
            summary="A summary",
            highlights=["a" * 1025]
        )
    assert "Item in list exceeds maximum length of 1024 characters" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        GitHubRepoContextPayload(
            normalized_repo_url="https://github.com/foo/bar",
            repo_full_name="foo/bar",
            summary="A summary",
            files_used=["valid", "b" * 1025]
        )
    assert "Item in list exceeds maximum length of 1024 characters" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        GitHubRepoContextPayload(
            normalized_repo_url="https://github.com/foo/bar",
            repo_full_name="foo/bar",
            summary="A summary",
            detected_stack=["c" * 2000]
        )
    assert "Item in list exceeds maximum length of 1024 characters" in str(exc_info.value)
