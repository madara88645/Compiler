import pytest
from unittest.mock import patch
from app.llm_engine.hybrid import HybridCompiler
from app.llm_engine.client import WorkerResponse
from app.models_v2 import IRv2


@pytest.fixture
def mock_worker_client():
    with patch("app.llm_engine.hybrid.WorkerClient") as mock:
        yield mock


@pytest.fixture
def mock_vector_db():
    with patch("app.llm_engine.hybrid.SQLiteVectorDB") as mock:
        yield mock


@pytest.fixture
def mock_context_strategist():
    with patch("app.llm_engine.hybrid.ContextStrategist") as mock:
        yield mock


@pytest.fixture
def compiler(mock_worker_client, mock_vector_db, mock_context_strategist):
    return HybridCompiler()


def test_init_defaults(mock_worker_client, mock_vector_db, mock_context_strategist):
    compiler = HybridCompiler()
    mock_worker_client.assert_called_once()
    mock_vector_db.assert_called_once()
    mock_context_strategist.assert_called_once()
    assert compiler.default_mode == "conservative"


def test_compile_empty_input(compiler):
    res = compiler.compile("")
    assert isinstance(res, WorkerResponse)
    assert res.thought_process == "Fallback to heuristics due to LLM error."
    assert any("Input was empty" in d.message for d in res.diagnostics)


def test_compile_cache_hit(compiler):
    text = "test query"
    res1 = WorkerResponse(
        ir=IRv2(
            language="en",
            persona="assistant",
            role="test",
            domain="general",
            output_format="text",
            length_hint="short",
        ),
        diagnostics=[],
        thought_process="Cached",
        optimized_content="content",
    )
    # Manually seed cache
    compiler.cache[(text, "conservative")] = res1

    # Compile
    res2 = compiler.compile(text)
    assert res2 is res1
    # Worker should not be called
    compiler.worker.process.assert_not_called()


@patch("app.llm_engine.hybrid.detect_risk_flags")
def test_compile_success(mock_detect_risk_flags, compiler):
    mock_detect_risk_flags.return_value = []
    text = "compile this"

    mock_ir = IRv2(
        language="en",
        persona="expert",
        role="tester",
        domain="general",
        output_format="text",
        length_hint="medium",
    )
    mock_res = WorkerResponse(
        ir=mock_ir, diagnostics=[], thought_process="Success", optimized_content="Optimized."
    )

    compiler.worker.process.return_value = mock_res
    compiler.context_strategist.process.return_value = "Mock context"

    res = compiler.compile(text)

    assert res is mock_res
    compiler.context_strategist.process.assert_called_once_with(text)
    compiler.worker.process.assert_called_once_with(
        text, context="Mock context", mode="conservative"
    )
    # Verify cached
    assert compiler.cache[(text, "conservative")] is mock_res


@patch("app.llm_engine.hybrid.detect_risk_flags")
def test_compile_with_risk_flags(mock_detect_risk_flags, compiler):
    # Test adding risk flags to diagnostics
    mock_detect_risk_flags.return_value = ["health", "financial", "legal", "security", "unknown"]
    text = "risky compile"

    mock_ir = IRv2(
        language="en",
        persona="expert",
        role="tester",
        domain="general",
        output_format="text",
        length_hint="medium",
    )
    mock_res = WorkerResponse(
        ir=mock_ir, diagnostics=[], thought_process="Success", optimized_content="Optimized."
    )

    compiler.worker.process.return_value = mock_res

    res = compiler.compile(text)

    # 4 diagnostics should be added
    assert len(res.diagnostics) == 4
    diag_messages = [d.message for d in res.diagnostics]
    assert any("Medical/Health" in m for m in diag_messages)
    assert any("Financial/Crypto" in m for m in diag_messages)
    assert any("Legal topic" in m for m in diag_messages)
    assert any("Security topic" in m for m in diag_messages)


def test_compile_worker_failure_fallback(compiler):
    text = "fail me"
    compiler.worker.process.side_effect = Exception("Worker Error")

    # Ensure fallback calls heuristics
    with patch("app.llm_engine.hybrid.compile_text_v2") as mock_compile_v2:
        mock_ir = IRv2(
            language="en",
            persona="assistant",
            role="test",
            domain="general",
            output_format="text",
            length_hint="medium",
        )
        mock_compile_v2.return_value = mock_ir

        res = compiler.compile(text)

        assert res.thought_process == "Fallback to heuristics due to LLM error."
        assert any("Worker Error" in d.message for d in res.diagnostics)
        assert res.ir is mock_ir


def test_compile_absolute_worst_case_fallback(compiler):
    text = "fail everything"
    compiler.worker.process.side_effect = Exception("Worker Error")

    # Mock compile_text_v2 to fail too
    with patch("app.llm_engine.hybrid.compile_text_v2", side_effect=Exception("Heuristics Error")):
        res = compiler.compile(text)

        assert res.thought_process == "System Failure"
        assert res.optimized_content == "Error."
        assert len(res.diagnostics) == 1
        assert "Heuristics Error" in res.diagnostics[0].message
        assert res.diagnostics[0].severity == "error"


def test_generate_agent_success(compiler):
    text = "make an agent"
    compiler.context_strategist.process.return_value = "Mock agent context"
    compiler.worker.generate_agent.return_value = "Agent System Prompt"

    res = compiler.generate_agent(text, multi_agent=True, include_example_code=True)

    assert res == "Agent System Prompt"
    compiler.context_strategist.process.assert_called_once_with(text)
    compiler.worker.generate_agent.assert_called_once_with(
        text, context="Mock agent context", multi_agent=True, include_example_code=True
    )


def test_generate_agent_failure(compiler):
    text = "fail agent"
    compiler.worker.generate_agent.side_effect = Exception("Agent Gen Error")

    res = compiler.generate_agent(text)

    assert "Failed to generate agent: Agent Gen Error" in res


def test_generate_skill_success(compiler):
    text = "make a skill"
    compiler.context_strategist.process.return_value = "Mock skill context"
    compiler.worker.generate_skill.return_value = "Skill Definition"

    res = compiler.generate_skill(text, include_example_code=True)

    assert res == "Skill Definition"
    compiler.context_strategist.process.assert_called_once_with(text)
    compiler.worker.generate_skill.assert_called_once_with(
        text, context="Mock skill context", include_example_code=True
    )


def test_generate_skill_failure(compiler):
    text = "fail skill"
    compiler.worker.generate_skill.side_effect = Exception("Skill Gen Error")

    res = compiler.generate_skill(text)

    assert "Failed to generate skill: Skill Gen Error" in res
