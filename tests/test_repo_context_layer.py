from app.repo_context import (
    github_payload_to_envelope,
    rag_results_to_envelope,
    render_repo_context_for_llm,
    sanitize_display_path,
)


GITHUB_PAYLOAD = {
    "normalized_repo_url": "https://github.com/openai/openai-python",
    "repo_full_name": "openai/openai-python",
    "requested_ref": None,
    "requested_subdir": None,
    "default_branch": "main",
    "summary": "Python SDK repo full summary content.",
    "summary_compact": "Python SDK repo compact summary content.",
    "highlights": ["Python package", "README present"],
    "files_used": ["README.md", "pyproject.toml"],
    "detected_stack": ["Python", "httpx"],
}


def test_github_payload_normalizes_to_repo_context_envelope():
    envelope = github_payload_to_envelope(GITHUB_PAYLOAD)

    assert envelope.source_type == "github_public"
    assert envelope.repo_identity.name == "openai/openai-python"
    assert envelope.repo_identity.url == "https://github.com/openai/openai-python"
    assert envelope.summary.full == "Python SDK repo full summary content."
    assert envelope.summary.compact == "Python SDK repo compact summary content."
    assert envelope.files_used == ["README.md", "pyproject.toml"]
    assert envelope.safety.path_safe is True
    assert envelope.safety.contains_absolute_paths is False


def test_renderer_uses_full_or_compact_summary():
    envelope = github_payload_to_envelope(GITHUB_PAYLOAD)

    compact = render_repo_context_for_llm(envelope, mode="compact")
    full = render_repo_context_for_llm(envelope, mode="full")

    assert "Python SDK repo compact summary content." in compact
    assert "Python SDK repo full summary content." not in compact
    assert "Python SDK repo full summary content." in full
    assert "Python SDK repo compact summary content." not in full


def test_rag_adapter_and_renderer_redact_absolute_paths():
    envelope = rag_results_to_envelope(
        [
            {
                "path": "/Users/memo/dev/project/app/auth.py",
                "snippet": "Read from /Users/memo/.promptc_uploads/secret.txt",
                "score": 0.9,
            },
            {
                "path": "C:\\Users\\memo\\dev\\project\\web\\page.tsx",
                "snippet": "Open C:\\Users\\memo\\.env",
                "score": 0.8,
            },
        ]
    )

    rendered = render_repo_context_for_llm(envelope, mode="full")

    assert "auth.py" in rendered
    assert "page.tsx" in rendered
    assert "/Users/" not in rendered
    assert "C:\\Users" not in rendered
    assert "C:/Users" not in rendered
    assert "[path-redacted]" in rendered
    assert envelope.safety.path_safe is True
    assert envelope.safety.contains_absolute_paths is False


def test_sanitize_display_path_keeps_relative_paths_and_strips_absolute_roots():
    assert sanitize_display_path("app/api/routes.py") == "app/api/routes.py"
    assert sanitize_display_path("/Users/memo/dev/project/app/api/routes.py") == "routes.py"
    assert sanitize_display_path("C:\\Users\\memo\\project\\app\\auth.py") == "auth.py"
