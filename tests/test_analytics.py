"""Tests for Analytics Module."""

import pytest
from app.reporting.analytics import extract_score_history, analyze_strategy_performance
from app.optimizer.models import OptimizationRun, OptimizationConfig, Candidate, EvaluationResult


@pytest.fixture
def mock_run():
    config = OptimizationConfig()
    run = OptimizationRun(config=config)

    # Gen 0
    c0 = Candidate(generation=0, prompt_text="Base", mutation_type="baseline")
    c0.result = EvaluationResult(
        score=0.5, passed_count=5, failed_count=5, error_count=0, avg_latency_ms=100
    )
    run.generations.append([c0])

    # Gen 1
    c1 = Candidate(generation=1, parent_id=c0.id, prompt_text="Mut1", mutation_type="compressor")
    c1.result = EvaluationResult(
        score=0.6, passed_count=6, failed_count=4, error_count=0, avg_latency_ms=90
    )

    c2 = Candidate(generation=1, parent_id=c0.id, prompt_text="Mut2", mutation_type="persona")
    c2.result = EvaluationResult(
        score=0.7, passed_count=7, failed_count=3, error_count=0, avg_latency_ms=110
    )

    run.generations.append([c1, c2])

    # Gen 2
    c3 = Candidate(generation=2, parent_id=c2.id, prompt_text="Mut3", mutation_type="cot")
    c3.result = EvaluationResult(
        score=0.8, passed_count=8, failed_count=2, error_count=0, avg_latency_ms=120
    )

    c4 = Candidate(generation=2, parent_id=c2.id, prompt_text="Mut4", mutation_type="compressor")
    c4.result = EvaluationResult(
        score=0.65, passed_count=6, failed_count=4, error_count=0, avg_latency_ms=80
    )

    run.generations.append([c3, c4])

    return run


def test_extract_score_history(mock_run):
    data = extract_score_history(mock_run)

    assert data["labels"] == ["Gen 0", "Gen 1", "Gen 2"]

    datasets = {d["label"]: d["data"] for d in data["datasets"]}

    # Max scores: Gen 0 = 0.5, Gen 1 = 0.7, Gen 2 = 0.8
    assert datasets["Max Score"] == [0.5, 0.7, 0.8]

    # Avg scores: Gen 0 = 0.5, Gen 1 = 0.65, Gen 2 = 0.725
    assert datasets["Average Score"] == pytest.approx([0.5, 0.65, 0.725])


def test_analyze_strategy_performance(mock_run):
    data = analyze_strategy_performance(mock_run)

    labels = data["labels"]
    datasets = {d["label"]: d["data"] for d in data["datasets"]}
    values = datasets["Average Score by Strategy"]

    # Strategies: compressor, persona, cot
    # Compressor: (0.6 + 0.65) / 2 = 0.625
    # Persona: 0.7 / 1 = 0.7
    # CoT: 0.8 / 1 = 0.8

    assert "compressor" in labels
    assert "persona" in labels
    assert "cot" in labels

    idx_comp = labels.index("compressor")
    assert values[idx_comp] == pytest.approx(0.625)

    idx_persona = labels.index("persona")
    assert values[idx_persona] == pytest.approx(0.7)

    idx_cot = labels.index("cot")
    assert values[idx_cot] == pytest.approx(0.8)
