"""
Validation Report Generator

Generates detailed validation reports in HTML, Markdown, and JSON formats.
Includes quality scores, issue summaries, recommendations, and visual charts.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.validator import ValidationResult


@dataclass
class ReportConfig:
    """Configuration for report generation"""

    title: str = "Prompt Validation Report"
    include_charts: bool = True
    include_recommendations: bool = True
    include_raw_data: bool = False
    show_strengths: bool = True
    theme: str = "light"  # light or dark


class ValidationReportGenerator:
    """Generate validation reports in various formats"""

    def __init__(self, config: Optional[ReportConfig] = None):
        """Initialize report generator with configuration"""
        self.config = config or ReportConfig()

    def generate_html_report(
        self, results: List[ValidationResult], prompts: List[str]
    ) -> str:
        """
        Generate HTML validation report

        Args:
            results: List of validation results
            prompts: List of original prompt texts

        Returns:
            HTML string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calculate aggregate stats
        avg_score = sum(r.score.total for r in results) / len(results) if results else 0
        total_errors = sum(r.errors for r in results)
        total_warnings = sum(r.warnings for r in results)
        total_info = sum(r.info for r in results)

        # Build HTML
        html_parts = [
            self._get_html_header(),
            self._get_html_styles(),
            '<body>',
            f'<div class="container">',
            f'<h1>{self.config.title}</h1>',
            f'<p class="timestamp">Generated: {timestamp}</p>',
            '<div class="summary-grid">',
            self._create_summary_card(
                "Overall Score",
                f"{avg_score:.1f}/100",
                self._get_score_color(avg_score),
            ),
            self._create_summary_card("Total Prompts", str(len(results)), "#3498db"),
            self._create_summary_card("Errors", str(total_errors), "#e74c3c"),
            self._create_summary_card("Warnings", str(total_warnings), "#f39c12"),
            "</div>",
        ]

        # Individual prompt reports
        for idx, (result, prompt) in enumerate(zip(results, prompts), 1):
            html_parts.append(self._create_prompt_section(idx, result, prompt))

        # Aggregate recommendations
        if self.config.include_recommendations and results:
            html_parts.append(self._create_recommendations_section(results))

        html_parts.extend(["</div>", "</body>", "</html>"])

        return "\n".join(html_parts)

    def generate_markdown_report(
        self, results: List[ValidationResult], prompts: List[str]
    ) -> str:
        """
        Generate Markdown validation report

        Args:
            results: List of validation results
            prompts: List of original prompt texts

        Returns:
            Markdown string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calculate aggregate stats
        avg_score = sum(r.score.total for r in results) / len(results) if results else 0
        total_errors = sum(r.errors for r in results)
        total_warnings = sum(r.warnings for r in results)

        md_parts = [
            f"# {self.config.title}",
            f"\n**Generated:** {timestamp}\n",
            "## Summary\n",
            f"- **Overall Score:** {avg_score:.1f}/100",
            f"- **Total Prompts:** {len(results)}",
            f"- **Total Errors:** {total_errors}",
            f"- **Total Warnings:** {total_warnings}\n",
        ]

        # Individual prompt reports
        for idx, (result, prompt) in enumerate(zip(results, prompts), 1):
            md_parts.extend(
                [
                    f"\n---\n",
                    f"## Prompt {idx}\n",
                    "### Scores\n",
                    f"- **Overall:** {result.score.total:.1f}/100",
                    f"- **Clarity:** {result.score.clarity:.1f}/100",
                    f"- **Specificity:** {result.score.specificity:.1f}/100",
                    f"- **Completeness:** {result.score.completeness:.1f}/100",
                    f"- **Consistency:** {result.score.consistency:.1f}/100\n",
                ]
            )

            # Issues
            if result.issues:
                md_parts.append("### Issues\n")
                for issue in result.issues:
                    severity_emoji = {
                        "error": "❌",
                        "warning": "⚠️",
                        "info": "ℹ️",
                    }[issue.severity]
                    md_parts.extend(
                        [
                            f"**{severity_emoji} {issue.severity.upper()}** - {issue.category}",
                            f"- {issue.message}",
                            f"- 💡 Suggestion: {issue.suggestion}\n",
                        ]
                    )

            # Strengths
            if self.config.show_strengths and result.strengths:
                md_parts.append("### Strengths\n")
                for strength in result.strengths:
                    md_parts.append(f"- ✓ {strength}")
                md_parts.append("")

            # Prompt preview
            preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
            md_parts.extend(["\n### Prompt Text\n", f"```\n{preview}\n```\n"])

        return "\n".join(md_parts)

    def generate_json_report(
        self, results: List[ValidationResult], prompts: List[str]
    ) -> Dict[str, Any]:
        """
        Generate JSON validation report

        Args:
            results: List of validation results
            prompts: List of original prompt texts

        Returns:
            Dictionary for JSON serialization
        """
        timestamp = datetime.now().isoformat()

        # Calculate aggregate stats
        avg_score = sum(r.score.total for r in results) / len(results) if results else 0

        report = {
            "title": self.config.title,
            "generated_at": timestamp,
            "summary": {
                "total_prompts": len(results),
                "average_score": round(avg_score, 2),
                "total_errors": sum(r.errors for r in results),
                "total_warnings": sum(r.warnings for r in results),
                "total_info": sum(r.info for r in results),
            },
            "prompts": [],
        }

        for idx, (result, prompt) in enumerate(zip(results, prompts), 1):
            prompt_report = {
                "index": idx,
                "prompt_text": prompt if self.config.include_raw_data else prompt[:200],
                "score": {
                    "total": round(result.score.total, 2),
                    "clarity": round(result.score.clarity, 2),
                    "specificity": round(result.score.specificity, 2),
                    "completeness": round(result.score.completeness, 2),
                    "consistency": round(result.score.consistency, 2),
                },
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "message": issue.message,
                        "suggestion": issue.suggestion,
                        "field": issue.field,
                    }
                    for issue in result.issues
                ],
                "strengths": result.strengths if self.config.show_strengths else [],
                "counts": {
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "info": result.info,
                },
            }
            report["prompts"].append(prompt_report)

        return report

    def _get_html_header(self) -> str:
        """Get HTML header"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt Validation Report</title>"""

    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML report"""
        if self.config.theme == "dark":
            bg_color = "#1e1e1e"
            text_color = "#e0e0e0"
            card_bg = "#2d2d2d"
            border_color = "#404040"
        else:
            bg_color = "#f5f5f5"
            text_color = "#333"
            card_bg = "#fff"
            border_color = "#ddd"

        return f"""
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: {bg_color};
            color: {text_color};
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            color: {text_color};
        }}
        .timestamp {{
            color: #888;
            margin-bottom: 30px;
            font-size: 0.9em;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-card {{
            background: {card_bg};
            border: 2px solid {border_color};
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            font-size: 0.9em;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
        }}
        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .prompt-section {{
            background: {card_bg};
            border: 2px solid {border_color};
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .prompt-section h2 {{
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .scores-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .score-item {{
            text-align: center;
            padding: 15px;
            background: {bg_color};
            border-radius: 8px;
        }}
        .score-item .label {{
            font-size: 0.85em;
            color: #888;
            text-transform: uppercase;
        }}
        .score-item .score {{
            font-size: 1.8em;
            font-weight: bold;
            margin-top: 5px;
        }}
        .issues-list {{
            margin: 20px 0;
        }}
        .issue {{
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid;
        }}
        .issue.error {{
            background: #fee;
            border-color: #e74c3c;
        }}
        .issue.warning {{
            background: #fef5e7;
            border-color: #f39c12;
        }}
        .issue.info {{
            background: #e8f4fd;
            border-color: #3498db;
        }}
        .issue-header {{
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .issue-suggestion {{
            color: #666;
            font-style: italic;
            margin-top: 8px;
        }}
        .strengths-list {{
            list-style: none;
            padding: 0;
        }}
        .strengths-list li {{
            padding: 10px;
            margin: 5px 0;
            background: #d5f4e6;
            border-left: 4px solid #27ae60;
            border-radius: 5px;
        }}
        .prompt-preview {{
            background: {bg_color};
            padding: 15px;
            border-radius: 8px;
            border: 1px solid {border_color};
            margin: 20px 0;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .recommendations {{
            background: {card_bg};
            border: 2px solid #3498db;
            border-radius: 10px;
            padding: 30px;
            margin-top: 40px;
        }}
        .recommendations h2 {{
            color: #3498db;
        }}
        .recommendation-item {{
            padding: 15px;
            margin: 10px 0;
            background: {bg_color};
            border-radius: 8px;
        }}
    </style>
</head>"""

    def _create_summary_card(self, title: str, value: str, color: str) -> str:
        """Create a summary card HTML"""
        return f"""
        <div class="summary-card">
            <h3>{title}</h3>
            <div class="value" style="color: {color};">{value}</div>
        </div>"""

    def _create_prompt_section(
        self, idx: int, result: ValidationResult, prompt: str
    ) -> str:
        """Create HTML section for a single prompt"""
        parts = [
            f'<div class="prompt-section">',
            f"<h2>Prompt {idx}</h2>",
            '<div class="scores-grid">',
            self._create_score_item("Overall", result.score.total),
            self._create_score_item("Clarity", result.score.clarity),
            self._create_score_item("Specificity", result.score.specificity),
            self._create_score_item("Completeness", result.score.completeness),
            self._create_score_item("Consistency", result.score.consistency),
            "</div>",
        ]

        # Issues
        if result.issues:
            parts.append('<div class="issues-list"><h3>Issues</h3>')
            for issue in result.issues:
                parts.append(
                    f'<div class="issue {issue.severity}">'
                    f'<div class="issue-header">'
                    f'{self._get_severity_icon(issue.severity)} '
                    f'{issue.severity.upper()} - {issue.category}'
                    f"</div>"
                    f"<div>{issue.message}</div>"
                    f'<div class="issue-suggestion">💡 {issue.suggestion}</div>'
                    f"</div>"
                )
            parts.append("</div>")

        # Strengths
        if self.config.show_strengths and result.strengths:
            parts.append('<h3>Strengths</h3><ul class="strengths-list">')
            for strength in result.strengths:
                parts.append(f"<li>✓ {strength}</li>")
            parts.append("</ul>")

        # Prompt preview
        preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
        parts.append(f'<h3>Prompt Text</h3><div class="prompt-preview">{preview}</div>')

        parts.append("</div>")
        return "\n".join(parts)

    def _create_score_item(self, label: str, score: float) -> str:
        """Create a score display item"""
        color = self._get_score_color(score)
        return f"""
        <div class="score-item">
            <div class="label">{label}</div>
            <div class="score" style="color: {color};">{score:.1f}</div>
        </div>"""

    def _create_recommendations_section(self, results: List[ValidationResult]) -> str:
        """Create aggregate recommendations section"""
        # Collect common issues
        issue_counts: Dict[str, int] = {}
        for result in results:
            for issue in result.issues:
                key = f"{issue.category}:{issue.severity}"
                issue_counts[key] = issue_counts.get(key, 0) + 1

        # Get top issues
        top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        parts = [
            '<div class="recommendations">',
            "<h2>💡 Top Recommendations</h2>",
            "<p>Based on analysis of all prompts, here are the most common issues:</p>",
        ]

        for (issue_key, count) in top_issues:
            category, severity = issue_key.split(":")
            parts.append(
                f'<div class="recommendation-item">'
                f"<strong>{count} prompt(s)</strong> have {severity} issues with <strong>{category}</strong>"
                f"</div>"
            )

        parts.append("</div>")
        return "\n".join(parts)

    def _get_severity_icon(self, severity: str) -> str:
        """Get icon for severity level"""
        icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        return icons.get(severity, "•")

    def _get_score_color(self, score: float) -> str:
        """Get color based on score"""
        if score >= 80:
            return "#27ae60"  # green
        elif score >= 60:
            return "#f39c12"  # orange
        else:
            return "#e74c3c"  # red


def get_report_generator(config: Optional[ReportConfig] = None) -> ValidationReportGenerator:
    """Get or create report generator instance"""
    return ValidationReportGenerator(config)
