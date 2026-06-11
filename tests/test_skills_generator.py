import re

import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient, _sanitize_skill_definition_plain
from app.llm_engine.hybrid import HybridCompiler
from api.main import app
from fastapi.testclient import TestClient


def _assert_plain_skill_output_is_clean(text: str) -> None:
    assert "```" not in text
    assert "**Examples**" not in text
    assert "**Examples:**" not in text
    assert "## Examples" not in text
    assert "### Examples" not in text
    assert re.search(r"^Examples:\s*$", text, flags=re.MULTILINE) is None
    assert 'Input: `{"' not in text
    assert "→ Output:" not in text
    assert "-> Output:" not in text


_SKILL_OUTPUT_WITH_EXAMPLES = """\
# json-validator - Skill Definition

## Name
json_validator

## Purpose
Validates JSON payloads.

## Implementation
1. Parse the payload.
2. Validate against schema rules.

## Examples
- Input: `{"data": "x"}` → Output: `{"valid": true}`

**Examples:**
```json
{"input": {"data": "x"}, "output": {"valid": true}}
```

## Implementation Example
```python
def run_skill(payload):
    return {"valid": True}
```

## Error Handling
- Return a structured error when JSON is invalid.
"""

_PREVIEW_STYLE_SKILL_OUTPUT = """\
# url-summarizer - Skill Definition

## Name
url_summarizer

## Purpose
**What:** Summarizes web page content from a URL.
**When to use:** Use when a user provides a URL and wants a short summary.

## Input Schema
- `url` (str): Public HTTP or HTTPS URL.

**Output Schema**
A JSON object with page metadata and summary text.

```json
{
  "title": "string",
  "summary": "string"
}
```

## Implementation
1. Validate the URL scheme.
2. Fetch and extract readable text.
3. Return a concise summary.

**Examples**

```json
{
  "input": {"url": "https://example.com"},
  "output": {"title": "Example Domain", "summary": "Illustrative example page."}
}
```

- Input: `{"url": "https://example.com"}` → Output: `{"title": "Example Domain", "summary": "..."}`

## Error Handling
- Reject unsupported URL schemes.
"""


# Mock WorkerClient to avoid API calls
@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as MockClient:
        client_instance = MockClient.return_value
        # Mock generate_skill method
        client_instance.generate_skill.return_value = "# Mock Skill Definition"
        yield client_instance


def test_worker_client_generate_skill():
    # Test the generate_skill method directly (mocking the API call inside it)
    with patch("app.llm_engine.client.OpenAI") as MockOpenAI:
        mock_openai_instance = MockOpenAI.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "# Skill Definition"
        mock_openai_instance.chat.completions.create.return_value = mock_completion

        client = WorkerClient(api_key="test")
        result = client.generate_skill("Test Skill")
        assert result == "# Skill Definition"


def test_hybrid_compiler_generate_skill(mock_worker_client):
    compiler = HybridCompiler()
    # Manually inject the mock worker because HybridCompiler creates its own instance
    compiler.worker = mock_worker_client
    repo_context = {
        "normalized_repo_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "default_branch": "main",
        "summary": "Python SDK repository.",
        "highlights": ["README present"],
        "files_used": ["README.md"],
        "detected_stack": ["Python"],
    }

    result = compiler.generate_skill("Test Skill", repo_context=repo_context)
    assert result == "# Mock Skill Definition"
    mock_worker_client.generate_skill.assert_called_once()
    args, kwargs = mock_worker_client.generate_skill.call_args
    assert args == ("Test Skill",)
    assert kwargs["include_example_code"] is False
    assert kwargs["context"]["repo_context"] == {
        "source": "github_public_repo",
        "mode": "full",
        **repo_context,
    }


def test_api_generate_skill_endpoint():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock API Skill"
        repo_context = {
            "normalized_repo_url": "https://github.com/openai/openai-python",
            "repo_full_name": "openai/openai-python",
            "default_branch": "main",
            "summary": "Python SDK repository.",
            "highlights": ["README present"],
            "files_used": ["README.md"],
            "detected_stack": ["Python"],
        }

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Test Skill Request", "repo_context": repo_context},
        )

        assert response.status_code == 200
        assert response.json() == {"skill_definition": "# Mock API Skill"}
        mock_compiler.generate_skill.assert_called_with(
            "Test Skill Request",
            include_example_code=False,
            repo_context={
                **repo_context,
                "summary_compact": None,
                "requested_ref": None,
                "requested_subdir": None,
            },
            repo_context_mode="full",
        )


def test_api_generate_skill_endpoint_with_example_code_enabled():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock API Skill"

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Test Skill Request", "include_example_code": True},
        )

        assert response.status_code == 200
        assert response.json() == {"skill_definition": "# Mock API Skill"}
        mock_compiler.generate_skill.assert_called_with(
            "Test Skill Request",
            include_example_code=True,
            repo_context=None,
            repo_context_mode="full",
        )


def test_skill_prompt_omits_examples_section_when_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    rendered = client._skill_prompt(include_example_code=False)

    assert "## Examples\n[At least one" not in rendered
    assert "Input: `{param_name:" not in rendered
    assert "## OPTIONAL IMPLEMENTATION EXAMPLE SECTION" not in rendered
    assert "Omit `## Examples` entirely" in rendered
    assert "Do not include fenced code blocks" in rendered


def test_worker_client_omits_skill_implementation_example_when_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode):
            captured["messages"] = messages
            return "# Skill Definition"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_skill("Test Skill", include_example_code=False)

        assert result == "# Skill Definition"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert any(
            "Example code is disabled for this request" in message for message in system_messages
        )
        assert any(
            "You MUST NOT include" in message and "`## Examples` section" in message
            for message in system_messages
        )
        assert any(
            "fenced code blocks" in message and "`## Implementation Example` section" in message
            for message in system_messages
        )


def test_sanitize_skill_definition_plain_removes_examples_and_code():
    cleaned = _sanitize_skill_definition_plain(_SKILL_OUTPUT_WITH_EXAMPLES)

    _assert_plain_skill_output_is_clean(cleaned)
    assert "## Implementation Example" not in cleaned
    assert "## Error Handling" in cleaned
    assert "## Implementation" in cleaned


def test_sanitize_skill_definition_plain_removes_preview_style_markdown():
    cleaned = _sanitize_skill_definition_plain(_PREVIEW_STYLE_SKILL_OUTPUT)

    _assert_plain_skill_output_is_clean(cleaned)
    assert "**Output Schema**" in cleaned
    assert "A JSON object with page metadata and summary text." in cleaned
    assert "## Error Handling" in cleaned


def test_generate_skill_sanitizes_plain_output_when_example_code_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        with patch.object(client, "_call_api", return_value=_PREVIEW_STYLE_SKILL_OUTPUT):
            result = client.generate_skill("Test Skill", include_example_code=False)

    _assert_plain_skill_output_is_clean(result)
    assert "**Output Schema**" in result
    assert "## Error Handling" in result


def test_api_generate_skill_plain_response_is_sanitized_at_route_boundary():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = _PREVIEW_STYLE_SKILL_OUTPUT

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={"description": "Summarize a web page from a URL"},
        )

        assert response.status_code == 200
        skill_definition = response.json()["skill_definition"]
        _assert_plain_skill_output_is_clean(skill_definition)
        assert "**Output Schema**" in skill_definition
        mock_compiler.generate_skill.assert_called_with(
            "Summarize a web page from a URL",
            include_example_code=False,
            repo_context=None,
            repo_context_mode="full",
        )


def test_api_generate_skill_preserves_examples_when_example_code_enabled():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = _PREVIEW_STYLE_SKILL_OUTPUT

        client = TestClient(app)
        response = client.post(
            "/skills-generator/generate",
            json={
                "description": "Summarize a web page from a URL",
                "include_example_code": True,
            },
        )

        assert response.status_code == 200
        skill_definition = response.json()["skill_definition"]
        assert "```json" in skill_definition
        assert "**Examples**" in skill_definition
        assert 'Input: `{"url"' in skill_definition


def test_generate_skill_preserves_examples_when_example_code_enabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        with patch.object(client, "_call_api", return_value=_SKILL_OUTPUT_WITH_EXAMPLES):
            result = client.generate_skill("Test Skill", include_example_code=True)

    assert "## Examples" in result
    assert "**Examples:**" in result
    assert "## Implementation Example" in result
    assert "```json" in result
    assert "```python" in result


def test_worker_client_requests_skill_implementation_example_when_enabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode):
            captured["messages"] = messages
            return "# Skill Definition"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_skill("Test Skill", include_example_code=True)

        assert result == "# Skill Definition"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert any(
            "Example code is enabled for this request" in message for message in system_messages
        )
        assert any(
            "You MUST include" in message and "`## Examples` section" in message
            for message in system_messages
        )
        assert any("`## Implementation Example` section" in message for message in system_messages)
