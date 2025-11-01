"""Tests for validation report generator."""

import pytest
import json
from pathlib import Path

from app.report_generator import (
    ValidationReportGenerator,
    ReportConfig,
    get_report_generator,
)
from app.validator import ValidationResult, QualityScore, ValidationIssue


@pytest.fixture
def sample_validation_result():
    """Create a sample validation result"""
    score = QualityScore(
        total=75.5, clarity=80.0, specificity=70.0, completeness=75.0, consistency=77.0
    )

    issues = [
        ValidationIssue(
            severity="error",
            category="clarity",
            message="Prompt is too vague",
            suggestion="Add specific details",
            field="prompt_text",
        ),
        ValidationIssue(
            severity="warning",
            category="completeness",
            message="Missing context",
            suggestion="Include background information",
            field=None,
        ),
    ]

    return ValidationResult(
        score=score,
        issues=issues,
        strengths=["Clear persona", "Good structure"],
        errors=1,
        warnings=1,
        info=0,
    )


@pytest.fixture
def sample_prompts():
    """Sample prompt texts"""
    return [
        "Write a tutorial about Python programming",
        "Explain machine learning concepts to beginners",
    ]


class TestReportConfig:
    """Tests for ReportConfig"""

    def test_default_config(self):
        """Test default configuration"""
        config = ReportConfig()

        assert config.title == "Prompt Validation Report"
        assert config.include_charts is True
        assert config.include_recommendations is True
        assert config.include_raw_data is False
        assert config.show_strengths is True
        assert config.theme == "light"

    def test_custom_config(self):
        """Test custom configuration"""
        config = ReportConfig(
            title="Custom Report",
            include_charts=False,
            theme="dark",
        )

        assert config.title == "Custom Report"
        assert config.include_charts is False
        assert config.theme == "dark"


class TestValidationReportGenerator:
    """Tests for ValidationReportGenerator"""

    def test_html_report_generation(self, sample_validation_result, sample_prompts):
        """Test HTML report generation"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result]

        html = generator.generate_html_report(results, sample_prompts[:1])

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "Prompt Validation Report" in html
        assert "75.5" in html  # Overall score
        assert "80.0" in html  # Clarity score
        assert "error" in html.lower()
        assert "warning" in html.lower()
        assert "Clear persona" in html

    def test_html_report_multiple_prompts(self, sample_validation_result, sample_prompts):
        """Test HTML report with multiple prompts"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result, sample_validation_result]

        html = generator.generate_html_report(results, sample_prompts)

        assert "Prompt 1" in html
        assert "Prompt 2" in html
        assert "Total Prompts" in html
        assert sample_prompts[0] in html
        assert sample_prompts[1] in html

    def test_html_report_dark_theme(self, sample_validation_result, sample_prompts):
        """Test HTML report with dark theme"""
        config = ReportConfig(theme="dark")
        generator = ValidationReportGenerator(config)

        html = generator.generate_html_report([sample_validation_result], sample_prompts[:1])

        assert "#1e1e1e" in html  # Dark background color
        assert "#e0e0e0" in html  # Light text color

    def test_markdown_report_generation(self, sample_validation_result, sample_prompts):
        """Test Markdown report generation"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result]

        md = generator.generate_markdown_report(results, sample_prompts[:1])

        assert "# Prompt Validation Report" in md
        assert "## Summary" in md
        assert "75.5" in md
        assert "### Scores" in md
        assert "### Issues" in md
        assert "❌" in md  # Error emoji
        assert "⚠️" in md  # Warning emoji
        assert "Clear persona" in md

    def test_markdown_report_no_strengths(self, sample_validation_result, sample_prompts):
        """Test Markdown report without strengths"""
        config = ReportConfig(show_strengths=False)
        generator = ValidationReportGenerator(config)

        md = generator.generate_markdown_report([sample_validation_result], sample_prompts[:1])

        assert "Clear persona" not in md
        assert "### Strengths" not in md

    def test_json_report_generation(self, sample_validation_result, sample_prompts):
        """Test JSON report generation"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result]

        report_dict = generator.generate_json_report(results, sample_prompts[:1])

        assert "title" in report_dict
        assert "summary" in report_dict
        assert "prompts" in report_dict

        assert report_dict["summary"]["total_prompts"] == 1
        assert report_dict["summary"]["average_score"] == 75.5
        assert report_dict["summary"]["total_errors"] == 1
        assert report_dict["summary"]["total_warnings"] == 1

        assert len(report_dict["prompts"]) == 1
        prompt_report = report_dict["prompts"][0]
        assert prompt_report["index"] == 1
        assert "score" in prompt_report
        assert "issues" in prompt_report
        assert "strengths" in prompt_report

    def test_json_report_with_raw_data(self, sample_validation_result, sample_prompts):
        """Test JSON report with raw data"""
        config = ReportConfig(include_raw_data=True)
        generator = ValidationReportGenerator(config)

        report_dict = generator.generate_json_report([sample_validation_result], sample_prompts[:1])

        # Should include full prompt text
        assert report_dict["prompts"][0]["prompt_text"] == sample_prompts[0]

    def test_json_report_without_raw_data(self, sample_validation_result, sample_prompts):
        """Test JSON report without raw data (truncated)"""
        config = ReportConfig(include_raw_data=False)
        generator = ValidationReportGenerator(config)

        long_prompt = "x" * 300
        report_dict = generator.generate_json_report([sample_validation_result], [long_prompt])

        # Should be truncated to 200 chars
        assert len(report_dict["prompts"][0]["prompt_text"]) == 200

    def test_score_color_calculation(self):
        """Test score color calculation"""
        generator = ValidationReportGenerator()

        # High score - green
        assert generator._get_score_color(85.0) == "#27ae60"

        # Medium score - orange
        assert generator._get_score_color(65.0) == "#f39c12"

        # Low score - red
        assert generator._get_score_color(45.0) == "#e74c3c"

        # Edge cases
        assert generator._get_score_color(80.0) == "#27ae60"
        assert generator._get_score_color(60.0) == "#f39c12"

    def test_severity_icon(self):
        """Test severity icon mapping"""
        generator = ValidationReportGenerator()

        assert generator._get_severity_icon("error") == "❌"
        assert generator._get_severity_icon("warning") == "⚠️"
        assert generator._get_severity_icon("info") == "ℹ️"
        assert generator._get_severity_icon("unknown") == "•"

    def test_aggregate_statistics(self, sample_validation_result):
        """Test aggregate statistics calculation"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result, sample_validation_result]
        prompts = ["prompt1", "prompt2"]

        html = generator.generate_html_report(results, prompts)

        # Check for aggregate values
        assert "Total Prompts" in html
        assert ">2<" in html  # Should show 2 prompts

    def test_recommendations_section(self, sample_validation_result):
        """Test recommendations section generation"""
        config = ReportConfig(include_recommendations=True)
        generator = ValidationReportGenerator(config)
        results = [sample_validation_result, sample_validation_result]
        prompts = ["prompt1", "prompt2"]

        html = generator.generate_html_report(results, prompts)

        assert "Top Recommendations" in html
        assert "recommendations" in html.lower()

    def test_no_recommendations(self, sample_validation_result):
        """Test report without recommendations"""
        config = ReportConfig(include_recommendations=False)
        generator = ValidationReportGenerator(config)

        html = generator.generate_html_report([sample_validation_result], ["prompt"])

        assert "Top Recommendations" not in html

    def test_empty_results(self):
        """Test handling empty results"""
        generator = ValidationReportGenerator()

        html = generator.generate_html_report([], [])
        md = generator.generate_markdown_report([], [])
        json_report = generator.generate_json_report([], [])

        assert "0/100" in html  # Average score should be 0
        assert "0.0" in md
        assert json_report["summary"]["total_prompts"] == 0


class TestGetReportGenerator:
    """Tests for get_report_generator function"""

    def test_get_default_generator(self):
        """Test getting default generator"""
        generator = get_report_generator()

        assert isinstance(generator, ValidationReportGenerator)
        assert generator.config.title == "Prompt Validation Report"

    def test_get_generator_with_config(self):
        """Test getting generator with custom config"""
        config = ReportConfig(title="Custom", theme="dark")
        generator = get_report_generator(config)

        assert generator.config.title == "Custom"
        assert generator.config.theme == "dark"


class TestReportIntegration:
    """Integration tests for report generation"""

    def test_full_report_workflow(self, sample_validation_result, tmp_path):
        """Test complete report generation workflow"""
        generator = ValidationReportGenerator()
        results = [sample_validation_result]
        prompts = ["Test prompt"]

        # Generate all formats
        html = generator.generate_html_report(results, prompts)
        md = generator.generate_markdown_report(results, prompts)
        json_report = generator.generate_json_report(results, prompts)

        # Save to files
        html_file = tmp_path / "report.html"
        md_file = tmp_path / "report.md"
        json_file = tmp_path / "report.json"

        html_file.write_text(html, encoding="utf-8")
        md_file.write_text(md, encoding="utf-8")
        json_file.write_text(json.dumps(json_report, indent=2), encoding="utf-8")

        # Verify files
        assert html_file.exists()
        assert md_file.exists()
        assert json_file.exists()

        # Verify content
        assert html_file.stat().st_size > 1000  # HTML should be substantial
        assert md_file.stat().st_size > 500
        assert json_file.stat().st_size > 200

    def test_batch_validation_report(self, sample_validation_result):
        """Test report for batch validation"""
        generator = ValidationReportGenerator()

        # Simulate 5 prompts
        results = [sample_validation_result] * 5
        prompts = [f"Prompt {i}" for i in range(1, 6)]

        html = generator.generate_html_report(results, prompts)

        # Check all prompts are included
        for i in range(1, 6):
            assert f"Prompt {i}" in html

        # Check aggregate statistics
        assert "5" in html  # Total count
