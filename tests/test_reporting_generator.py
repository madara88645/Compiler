import json
import re
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


def test_generate_report_escapes_untrusted_html_content(tmp_path):
    config = OptimizationConfig(model="gpt-4o")
    baseline = Candidate(
        id="baseline",
        generation=0,
        prompt_text="baseline prompt",
        result=EvaluationResult(
            score=0.4, passed_count=4, failed_count=6, error_count=0, avg_latency_ms=100.0
        ),
    )
    best = Candidate(
        id="best",
        generation=1,
        prompt_text="<img src=x onerror=alert(1)>",
        mutation_type="<svg/onload=alert(3)>",
        metadata={"validation_scores": {"<script>alert(4)</script>": 0.6}},
        result=EvaluationResult(
            score=0.8,
            passed_count=8,
            failed_count=2,
            error_count=0,
            avg_latency_ms=120.0,
            failures=["<script>alert(2)</script>"],
        ),
    )
    run = OptimizationRun(
        id="test-run-escaped",
        config=config,
        created_at=datetime.now(),
        generations=[[baseline], [best]],
        best_candidate=best,
    )

    output_path = tmp_path / "report_escaped.html"
    ReportGenerator().generate_report(run, output_path)

    html_content = output_path.read_text(encoding="utf-8")

    assert "<img src=x onerror=alert(1)>" not in html_content
    assert "<script>alert(2)</script>" not in html_content
    assert "<svg/onload=alert(3)>" not in html_content
    assert "<script>alert(4)</script>" not in html_content
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_content
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html_content
    assert "&lt;svg/onload=alert(3)&gt;" in html_content
    assert "&lt;script&gt;alert(4)&lt;/script&gt;" in html_content


def test_generate_report_preserves_chart_json_literals(tmp_path):
    config = OptimizationConfig(model="gpt-4o")
    baseline = Candidate(
        id="baseline",
        generation=0,
        prompt_text="baseline prompt",
        result=EvaluationResult(
            score=0.4, passed_count=4, failed_count=6, error_count=0, avg_latency_ms=100.0
        ),
    )
    best = Candidate(
        id="best",
        generation=1,
        prompt_text="improved prompt",
        result=EvaluationResult(
            score=0.8, passed_count=8, failed_count=2, error_count=0, avg_latency_ms=120.0
        ),
    )
    run = OptimizationRun(
        id="test-run-chart",
        config=config,
        created_at=datetime.now(),
        generations=[[baseline], [best]],
        best_candidate=best,
    )

    output_path = tmp_path / "report_chart.html"
    ReportGenerator().generate_report(run, output_path)

    html_content = output_path.read_text(encoding="utf-8")

    scores_match = re.search(r"const scores = (\[.*?\]);", html_content)
    labels_match = re.search(r"const labels = (\[.*?\]);", html_content)

    assert scores_match is not None
    assert labels_match is not None
    assert json.loads(scores_match.group(1)) == [0.4, 0.8]
    assert json.loads(labels_match.group(1)) == ["Gen 0", "Gen 1"]
