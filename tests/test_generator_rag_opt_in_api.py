"""Generator RAG context retrieval is opt-in (default off) — session isolation guard."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_agent_generator_does_not_retrieve_by_default():
    with patch("api.routes.generators._get_compiler") as get_compiler:
        compiler = MagicMock()
        compiler.generate_agent.return_value = "# Safe Agent"
        get_compiler.return_value = compiler

        resp = client.post(
            "/agent-generator/generate",
            json={"description": "Build a helpful coding agent"},
        )

        assert resp.status_code == 200
        _, kwargs = compiler.generate_agent.call_args
        assert kwargs.get("enable_context_retrieval") is False


def test_skill_generator_does_not_retrieve_by_default():
    with patch("api.routes.generators._get_compiler") as get_compiler:
        compiler = MagicMock()
        compiler.generate_skill.return_value = "# Safe Skill"
        get_compiler.return_value = compiler

        resp = client.post(
            "/skills-generator/generate",
            json={"description": "Build a helpful coding skill"},
        )

        assert resp.status_code == 200
        _, kwargs = compiler.generate_skill.call_args
        assert kwargs.get("enable_context_retrieval") is False


def test_agent_generator_opt_in_enables_retrieval():
    with patch("api.routes.generators._get_compiler") as get_compiler:
        compiler = MagicMock()
        compiler.generate_agent.return_value = "# Agent With Context"
        get_compiler.return_value = compiler

        resp = client.post(
            "/agent-generator/generate",
            json={
                "description": "Build a helpful coding agent",
                "enable_context_retrieval": True,
            },
        )

        assert resp.status_code == 200
        _, kwargs = compiler.generate_agent.call_args
        assert kwargs.get("enable_context_retrieval") is True


def test_skill_generator_opt_in_enables_retrieval():
    with patch("api.routes.generators._get_compiler") as get_compiler:
        compiler = MagicMock()
        compiler.generate_skill.return_value = "# Skill With Context"
        get_compiler.return_value = compiler

        resp = client.post(
            "/skills-generator/generate",
            json={
                "description": "Build a helpful coding skill",
                "enable_context_retrieval": True,
            },
        )

        assert resp.status_code == 200
        _, kwargs = compiler.generate_skill.call_args
        assert kwargs.get("enable_context_retrieval") is True


@patch("app.llm_engine.hybrid.ContextStrategist")
def test_hybrid_generators_skip_persisted_index_unless_opted_in(mock_strategist_cls):
    strategist = MagicMock()
    strategist.process.return_value = {
        "snippets": [{"file": "stale_session.md", "content": "secret from prior session"}]
    }
    mock_strategist_cls.return_value = strategist

    with patch("app.llm_engine.hybrid.WorkerClient") as mock_worker_cls:
        worker = MagicMock()
        worker.generate_agent.return_value = "# Agent"
        worker.generate_skill.return_value = "# Skill"
        mock_worker_cls.return_value = worker

        from app.llm_engine.hybrid import HybridCompiler

        compiler = HybridCompiler()

        compiler.generate_agent("new session request")
        strategist.process.assert_not_called()
        _, agent_kwargs = worker.generate_agent.call_args
        assert agent_kwargs.get("context") is None

        compiler.generate_skill("new session request")
        strategist.process.assert_not_called()
        _, skill_kwargs = worker.generate_skill.call_args
        assert skill_kwargs.get("context") is None

        compiler.generate_agent("new session request", enable_context_retrieval=True)
        strategist.process.assert_called_with("new session request", expand_with_llm=False)
