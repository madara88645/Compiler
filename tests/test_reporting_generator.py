from datetime import datetime
from app.reporting.generator import ReportGenerator
from app.optimizer.models import OptimizationRun, OptimizationConfig, Candidate, EvaluationResult


def test_generate_report_success(tmp_path):
    # Setup optimization run data
    config = OptimizationConfig(
        max_generations=2,
        candidates_per_generation=2,
        target_score=0.9,
        model="gpt-4o",
    )

    # Generation 0
    c0_1 = Candidate(
        id="c0_1",
        generation=0,
        prompt_text="baseline prompt",
        mutation_type="initial",
        result=EvaluationResult(
            score=0.5,
            passed_count=5,
            failed_count=5,
            error_count=0,
            avg_latency_ms=100.0,
            failures=["Failed test 1"],
        ),
    )

    # Generation 1
    c1_1 = Candidate(
        id="c1_1",
        generation=1,
        prompt_text="improved prompt",
        mutation_type="persona",
        metadata={
            "validation_scores": {
                "claude-3-5-sonnet": 0.8,
                "gpt-4-mini": 0.4,  # overfit (0.9 - 0.4 = 0.5 > 0.2)
            }
        },
        result=EvaluationResult(
            score=0.9,
            passed_count=9,
            failed_count=1,
            error_count=0,
            avg_latency_ms=150.0,
            failures=["Failed test 2"],
        ),
    )

    run = OptimizationRun(
        id="test-run-id-123456",
        config=config,
        created_at=datetime.now(),
        generations=[[c0_1], [c1_1]],
        best_candidate=c1_1,
    )

    output_path = tmp_path / "report.html"
    generator = ReportGenerator()
    generator.generate_report(run, output_path)

    assert output_path.exists()
    html_content = output_path.read_text(encoding="utf-8")

    # Assert key components exist in the HTML report
    assert "test-run-id-123456" in html_content
    assert "improved prompt" in html_content
    assert "gpt-4o" in html_content
    assert "claude-3-5-sonnet" in html_content
    assert "OVERFIT" in html_content
    assert "Failed test 2" in html_content


def test_generate_report_fallback_best_candidate(tmp_path):
    # Test fallback detection of best candidate when run.best_candidate is None
    config = OptimizationConfig(model="gpt-4o")
    c0 = Candidate(
        id="c0",
        generation=0,
        prompt_text="baseline",
        result=EvaluationResult(
            score=0.4, passed_count=4, failed_count=6, error_count=0, avg_latency_ms=100.0
        ),
    )
    c1 = Candidate(
        id="c1",
        generation=1,
        prompt_text="improved",
        result=EvaluationResult(
            score=0.8, passed_count=8, failed_count=2, error_count=0, avg_latency_ms=100.0
        ),
    )

    run = OptimizationRun(
        id="test-run-id-fallback",
        config=config,
        generations=[[c0], [c1]],
        best_candidate=None,  # Force fallback scan
    )

    output_path = tmp_path / "report_fallback.html"
    generator = ReportGenerator()
    generator.generate_report(run, output_path)

    assert output_path.exists()
    html_content = output_path.read_text(encoding="utf-8")
    assert "test-run-id-fallback" in html_content


def test_generate_report_insufficient_data(tmp_path, capsys):
    # Test graceful warning when there is no data in the run
    config = OptimizationConfig(model="gpt-4o")
    run = OptimizationRun(id="test-run-empty", config=config, generations=[], best_candidate=None)

    output_path = tmp_path / "report_empty.html"
    generator = ReportGenerator()
    generator.generate_report(run, output_path)

    assert not output_path.exists()

    captured = capsys.readouterr()
    assert "Warning: Insufficient data to generate full report." in captured.out
