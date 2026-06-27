"""
Tests to verify that public endpoints work without API keys but are still rate-limited.

These tests verify the fix for the production issue where /benchmark/run,
/skills-generator/generate, and /agent-generator/generate were requiring
API keys, blocking public access.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client_without_auth_override():
    """
    Create a test client that does NOT override auth dependencies.

    This ensures we're testing the actual endpoint behavior without
    the test suite's automatic auth bypass.
    """
    # Clear any existing overrides
    app.dependency_overrides.clear()
    client = TestClient(app)
    yield client
    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.auth_required
@pytest.mark.skip(reason='Security enhancement: benchmark now requires auth')
def test_benchmark_endpoint_works_without_api_key(client_without_auth_override):
    """
    /benchmark/run should work without API key authentication.
    """
    with patch("app.routers.benchmark._generate_llm_output") as mock_llm, patch(
        "app.routers.benchmark._judge_with_llm", return_value=None
    ):
        mock_llm.side_effect = ["raw output", "compiled output"]

        response = client_without_auth_override.post(
            "/benchmark/run",
            json={"text": "Test prompt", "model": "openai/gpt-oss-20b"},
        )

    # Should succeed without credentials
    assert response.status_code == 200
    data = response.json()
    assert "raw_output" in data
    assert "compiled_output" in data
    assert "winner" in data


@pytest.mark.auth_required
def test_skills_generator_works_without_api_key(client_without_auth_override):
    """
    /skills-generator/generate should work without API key authentication.
    """
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_skill.return_value = "# Mock Skill Definition"

        response = client_without_auth_override.post(
            "/skills-generator/generate",
            json={"description": "Test skill request"},
        )

    # Should succeed without credentials
    assert response.status_code == 200
    data = response.json()
    assert "skill_definition" in data
    assert data["skill_definition"] == "# Mock Skill Definition"


@pytest.mark.auth_required
def test_agent_generator_works_without_api_key(client_without_auth_override):
    """
    /agent-generator/generate should work without API key authentication.
    """
    with patch("api.main.hybrid_compiler") as mock_compiler:
        mock_compiler.generate_agent.return_value = "# Mock Agent System Prompt"

        response = client_without_auth_override.post(
            "/agent-generator/generate",
            json={"description": "Test agent request"},
        )

    # Should succeed without credentials
    assert response.status_code == 200
    data = response.json()
    assert "system_prompt" in data
    assert data["system_prompt"] == "# Mock Agent System Prompt"


@pytest.mark.auth_required
def test_public_endpoints_have_rate_limiting(client_without_auth_override):
    """
    Verify that public endpoints are still protected by IP rate limiting.

    This test ensures we didn't accidentally remove rate limiting when
    removing API key requirements.
    """
    # Check that the endpoints have rate_limit_by_ip dependency
    from app.routers.benchmark import benchmark_run
    from api.routes.generators import generate_skill_endpoint, generate_agent_endpoint

    # These endpoints should have rate_limit_by_ip in their dependencies
    # We can't easily test the actual rate limiting without making many requests,
    # but we can verify the dependency is present by checking the function signature
    import inspect

    # Check benchmark endpoint
    benchmark_sig = inspect.signature(benchmark_run)
    assert any(
        param.name == "_" for param in benchmark_sig.parameters.values()
    ), "benchmark_run should have rate limit dependency"

    # Check skills generator endpoint
    skills_sig = inspect.signature(generate_skill_endpoint)
    assert any(
        param.name == "_" for param in skills_sig.parameters.values()
    ), "generate_skill_endpoint should have rate limit dependency"

    # Check agent generator endpoint
    agent_sig = inspect.signature(generate_agent_endpoint)
    assert any(
        param.name == "_" for param in agent_sig.parameters.values()
    ), "generate_agent_endpoint should have rate limit dependency"
