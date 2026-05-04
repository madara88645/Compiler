import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.client import WorkerClient
from app.llm_engine.hybrid import HybridCompiler
from api.main import app
from fastapi.testclient import TestClient


# Mock WorkerClient to avoid API calls
@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as MockClient:
        client_instance = MockClient.return_value
        # Mock generate_agent method
        client_instance.generate_agent.return_value = "# Mock Agent System Prompt"
        yield client_instance


def test_worker_client_generate_agent():
    # Test the generate_agent method directly (mocking the API call inside it)
    with patch("app.llm_engine.client.OpenAI") as MockOpenAI:
        mock_openai_instance = MockOpenAI.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "# Agent System Prompt"
        mock_openai_instance.chat.completions.create.return_value = mock_completion

        client = WorkerClient(api_key="test")
        result = client.generate_agent("Test Agent")
        assert result == "# Agent System Prompt"


def test_hybrid_compiler_generate_agent(mock_worker_client):
    compiler = HybridCompiler()
    # Manually inject the mock worker because HybridCompiler creates its own instance
    compiler.worker = mock_worker_client

    result = compiler.generate_agent("Test Agent")
    assert result == "# Mock Agent System Prompt"
    # HybridCompiler now injects context, so we expect the context argument
    # We can use ANY for the context content since it depends on the mock vector db
    from unittest.mock import ANY

    mock_worker_client.generate_agent.assert_called_with(
        "Test Agent", context=ANY, multi_agent=False, include_example_code=False
    )


def test_worker_client_omits_example_code_section_when_disabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode):
            captured["messages"] = messages
            return "# Agent System Prompt"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_agent("Test Agent", include_example_code=False)

        assert result == "# Agent System Prompt"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert "## Example Code (Pseudo-code Skeleton)" not in system_messages[0]
        assert any(
            "Do not include fenced code blocks or pseudo-code" in message
            for message in system_messages
        )


def test_worker_client_requests_example_code_section_when_enabled():
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

        captured = {}

        def fake_call_api(messages, max_tokens, json_mode):
            captured["messages"] = messages
            return "# Agent System Prompt"

        with patch.object(client, "_call_api", side_effect=fake_call_api):
            result = client.generate_agent("Test Agent", include_example_code=True)

        assert result == "# Agent System Prompt"
        system_messages = [
            msg["content"] for msg in captured["messages"] if msg["role"] == "system"
        ]
        assert "## Example Code (Pseudo-code Skeleton)" in system_messages[0]
        assert any(
            "Include a final `## Example Code (Pseudo-code Skeleton)` section" in message
            for message in system_messages
        )


def test_api_generate_agent_endpoint():
    # Mock the global hybrid_compiler in api.main
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock API Agent"

        client = TestClient(app)
        response = client.post(
            "/agent-generator/generate", json={"description": "Test Agent Request"}
        )

        assert response.status_code == 200
        assert response.json() == {"system_prompt": "# Mock API Agent"}
        mock_compiler.generate_agent.assert_called_with(
            "Test Agent Request", multi_agent=False, include_example_code=False
        )


def test_api_generate_agent_endpoint_with_example_code_enabled():
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock API Agent"

        client = TestClient(app)
        response = client.post(
            "/agent-generator/generate",
            json={"description": "Test Agent Request", "include_example_code": True},
        )

        assert response.status_code == 200
        assert response.json() == {"system_prompt": "# Mock API Agent"}
        mock_compiler.generate_agent.assert_called_with(
            "Test Agent Request", multi_agent=False, include_example_code=True
        )


# ── New section-coverage regression tests ─────────────────────────────────────


def test_single_agent_template_includes_new_sections():
    """Rendered single-agent prompt must instruct the LLM to generate the three new sections."""
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    # Both enabled and disabled example-code modes should include the new sections.
    for include_example_code in (True, False):
        rendered = client._single_agent_prompt(include_example_code)
        assert (
            "## Tools & Integrations" in rendered
        ), f"Missing '## Tools & Integrations' (include_example_code={include_example_code})"
        assert (
            "## Stop Conditions" in rendered
        ), f"Missing '## Stop Conditions' (include_example_code={include_example_code})"
        assert (
            "## Self-Verification" in rendered
        ), f"Missing '## Self-Verification' (include_example_code={include_example_code})"


def test_multi_agent_template_includes_topology_and_io():
    """Rendered multi-agent prompt must instruct the LLM to declare topology, per-agent I/O, and swarm stop conditions."""
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    for include_example_code in (True, False):
        rendered = client._multi_agent_prompt(include_example_code)
        assert (
            "> **Topology:**" in rendered
        ), f"Missing '> **Topology:**' declaration guidance (include_example_code={include_example_code})"
        assert (
            "## Inputs" in rendered
        ), f"Missing '## Inputs' (include_example_code={include_example_code})"
        assert (
            "## Outputs" in rendered
        ), f"Missing '## Outputs' (include_example_code={include_example_code})"
        assert (
            "## Swarm Stop Conditions" in rendered
        ), f"Missing '## Swarm Stop Conditions' (include_example_code={include_example_code})"


def test_example_code_strip_still_works():
    """Disabling example code must strip the skeleton section but leave new sections intact."""
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    single_no_code = client._single_agent_prompt(include_example_code=False)
    assert "## Example Code (Pseudo-code Skeleton)" not in single_no_code
    assert "## Tools & Integrations" in single_no_code
    assert "## Self-Verification" in single_no_code

    multi_no_code = client._multi_agent_prompt(include_example_code=False)
    # The EXAMPLE CODE SETTING note mentions "## Swarm Example Code" in its anti-instruction,
    # so check the full skeleton header (with the disambiguation suffix) is absent instead.
    assert "## Swarm Example Code (Pseudo-code Skeleton)" not in multi_no_code
    assert "## Inputs" in multi_no_code
    assert "## Swarm Stop Conditions" in multi_no_code
