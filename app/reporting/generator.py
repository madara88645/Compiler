from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from jinja2 import Template

from app.optimizer.models import OptimizationRun

REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimization Report - {{ run.id[:8] }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .diff-add { background-color: #d1fae5; color: #065f46; }
        .diff-del { background-color: #fee2e2; color: #991b1b; text-decoration: line-through; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans">

    <!-- Header -->
    <header class="bg-white shadow-sm sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold text-indigo-600">Prompt Optimization Report</h1>
                <p class="text-sm text-gray-500">Run ID: {{ run.id }} | {{ timestamp }}</p>
            </div>
            <div class="flex space-x-4 text-sm">
                <div class="text-center">
                    <span class="block font-bold text-gray-900">{{ run.generations|length }}</span>
                    <span class="text-gray-500">Generations</span>
                </div>
                <div class="text-center">
                    <span class="block font-bold text-green-600">{{ "%.2f"|format(best_candidate.score) }}</span>
                    <span class="text-gray-500">Best Score</span>
                </div>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                <h3 class="text-lg font-semibold mb-2 text-gray-700">Configuration</h3>
                <ul class="text-sm space-y-1 text-gray-600">
                    <li><span class="font-medium">Model:</span> {{ run.config.model }}</li>
                    <li><span class="font-medium">Target Score:</span> {{ run.config.target_score }}</li>
                    <li><span class="font-medium">Max Gens:</span> {{ run.config.max_generations }}</li>
                </ul>
            </div>
            <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                <h3 class="text-lg font-semibold mb-2 text-gray-700">Improvement</h3>
                <div class="flex items-end space-x-2">
                    <span class="text-3xl font-bold text-green-500">
                        {{ "%.1f"|format((best_candidate.score - baseline_candidate.score) * 100) }}%
                    </span>
                    <span class="text-sm text-gray-500 mb-1">increase from baseline</span>
                </div>
                <div class="mt-2 text-xs text-gray-400">
                    Baseline: {{ "%.2f"|format(baseline_candidate.score) }} → Best: {{ "%.2f"|format(best_candidate.score) }}
                </div>
            </div>
            <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                <h3 class="text-lg font-semibold mb-2 text-gray-700">Evolution Chart</h3>
                <canvas id="scoreChart" height="100"></canvas>
            </div>
        </div>

        {% if robustness_data %}
        <!-- Robustness Matrix -->
        <section class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-200 bg-indigo-50">
                <h2 class="text-lg font-medium text-indigo-900">🛡️ Cross-Model Robustness Matrix</h2>
            </div>
            <div class="p-6 overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="bg-gray-50 text-gray-500">
                            <th class="px-4 py-2 text-left">Prompt ID</th>
                            <th class="px-4 py-2 text-center text-indigo-600 font-bold">Main ({{ run.config.model }})</th>
                            <th class="px-4 py-2 text-left">Validation Models</th>
                            <th class="px-4 py-2 text-left">Confidence</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                        {% for row in robustness_data %}
                        <tr>
                            <td class="px-4 py-3 font-mono text-xs text-gray-600">
                                {{ row.id }} <span class="text-gray-400">({{ row.mutation_type }})</span>
                            </td>
                            <td class="px-4 py-3 text-center font-bold text-gray-900">
                                {{ "%.2f"|format(row.main_score) }}
                            </td>
                            <td class="px-4 py-3">
                                <div class="flex space-x-4">
                                {% for val in row.validations %}
                                    <div class="text-xs">
                                        <span class="text-gray-500">{{ val.model }}:</span>
                                        <span class="font-medium {{ 'text-red-600 font-bold' if val.is_overfit else 'text-gray-700' }}">
                                            {{ "%.2f"|format(val.score) }}
                                        </span>
                                        {% if val.is_overfit %}
                                        <span class="text-[10px] text-red-500 bg-red-50 px-1 rounded border border-red-100 ml-1">OVERFIT</span>
                                        {% endif %}
                                    </div>
                                {% endfor %}
                                </div>
                            </td>
                            <td class="px-4 py-3">
                                {% if row.robustness_label == 'Low' %}
                                <span class="px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full font-bold">Low</span>
                                {% else %}
                                <span class="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full font-bold">High</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </section>
        {% endif %}

        <!-- Best Prompt Section -->
        <section class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-200 bg-indigo-50 flex justify-between items-center">
                <h2 class="text-lg font-medium text-indigo-900">🏆 Best Candidate (Gen {{ best_candidate.generation }})</h2>
                <span class="px-3 py-1 bg-indigo-100 text-indigo-800 text-xs rounded-full uppercase tracking-wide font-bold">
                    {{ best_candidate.mutation_type }}
                </span>
            </div>
            <div class="p-6">
                <pre class="bg-gray-800 text-gray-100 p-4 rounded-md text-sm font-mono overflow-auto max-h-[500px]">{{ best_candidate.prompt_text }}</pre>

                {% if best_candidate.result and best_candidate.result.failures %}
                <div class="mt-4 p-4 bg-yellow-50 rounded-md border border-yellow-200">
                    <h4 class="text-sm font-bold text-yellow-800 mb-2">Remaining Failures ({{ best_candidate.result.failed_count }})</h4>
                    <ul class="list-disc list-inside text-xs text-yellow-700 space-y-1">
                        {% for fail in best_candidate.result.failures[:5] %}
                        <li>{{ fail }}</li>
                        {% endfor %}
                        {% if best_candidate.result.failures|length > 5 %}
                        <li>... and {{ best_candidate.result.failures|length - 5 }} more</li>
                        {% endif %}
                    </ul>
                </div>
                {% endif %}
            </div>
        </section>

        <!-- Evolution Timeline -->
        <section>
            <h2 class="text-xl font-bold text-gray-800 mb-4">Evolution Timeline</h2>
            <div class="space-y-4">
                {% for gen in run.generations %}
                {% set top_cand = gen | sort(attribute='score', reverse=True) | first %}
                <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-200 transition hover:shadow-md">
                    <div class="flex justify-between items-start cursor-pointer" onclick="document.getElementById('gen-{{ loop.index0 }}').classList.toggle('hidden')">
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-gray-100 rounded-full font-bold text-gray-600 text-sm">
                                {{ loop.index0 }}
                            </div>
                            <div>
                                <h4 class="text-sm font-bold text-gray-900">Generation {{ loop.index0 }}</h4>
                                <p class="text-xs text-gray-500">Top Score: <span class="text-green-600 font-medium">{{ "%.2f"|format(top_cand.score) }}</span> ({{ gen|length }} candidates)</p>
                            </div>
                        </div>
                        <div class="text-gray-400">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>

                    <div id="gen-{{ loop.index0 }}" class="hidden mt-4 pt-4 border-t border-gray-100 grid grid-cols-1 gap-4">
                        {% for cand in gen %}
                        <div class="text-sm border-l-2 {{ 'border-green-500' if cand.id == top_cand.id else 'border-gray-300' }} pl-3">
                            <div class="flex justify-between">
                                <span class="font-mono text-xs text-gray-500">{{ cand.id }} ({{ cand.mutation_type }})</span>
                                <span class="font-bold {{ 'text-green-600' if cand.score >= 1.0 else 'text-gray-700' }}">{{ "%.2f"|format(cand.score) }}</span>
                            </div>
                            <div class="mt-1 text-gray-600 italic text-xs truncate">
                                {{ cand.prompt_text[:100] }}...
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

    </main>

    <footer class="bg-white border-t border-gray-200 mt-12 py-8">
        <div class="max-w-7xl mx-auto px-4 text-center text-gray-400 text-sm">
            Generated by Prompt Compiler | {{ timestamp }}
        </div>
    </footer>

    <script>
        const ctx = document.getElementById('scoreChart').getContext('2d');
        const scores = {{ scores_json }};
        const labels = {{ labels_json }};

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Best Score per Generation',
                    data: scores,
                    borderColor: 'rgb(79, 70, 229)',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, max: 1.0 }
                }
            }
        });
    </script>
</body>
</html>
"""


class ReportGenerator:
    """Generates HTML reports for optimization runs."""

    def generate_report(self, run: OptimizationRun, output_path: Path) -> None:
        """
        Compile the optimization run data into a single HTML report.

        Args:
            run: The OptimizationRun object containing all data.
            output_path: Path to write the HTML file.
        """
        # Prepare data
        baseline_candidate = run.generations[0][0] if run.generations else None

        # Determine best candidate (if not explicitly set in run, find it)
        best_candidate = run.best_candidate
        if not best_candidate and run.generations:
            # Fallback scan
            best_candidate = max(
                (c for gen in run.generations for c in gen),
                key=lambda x: x.score,
                default=baseline_candidate,
            )

        if not baseline_candidate or not best_candidate:
            # Should not happen in valid run, but handle gracefully
            print("Warning: Insufficient data to generate full report.")
            return

        # Prepare chart data
        labels = [f"Gen {i}" for i in range(len(run.generations))]
        # Get max score for each generation
        scores = [max(c.score for c in gen) if gen else 0.0 for gen in run.generations]

        # Robustness Data Preparation
        robustness_data = []
        for gen in run.generations:
            for cand in gen:
                # Check for validations
                if cand.metadata and "validation_scores" in cand.metadata:
                    val_scores = cand.metadata["validation_scores"]
                    if not val_scores:
                        continue

                    validations = []
                    any_overfit = False

                    for model, score in val_scores.items():
                        # Detect Overfit
                        diff = cand.score - score
                        is_overfit = diff > 0.2
                        if is_overfit:
                            any_overfit = True

                        validations.append(
                            {"model": model, "score": score, "is_overfit": is_overfit}
                        )

                    robustness_data.append(
                        {
                            "id": cand.id,
                            "mutation_type": cand.mutation_type,
                            "main_score": cand.score,
                            "validations": validations,
                            "robustness_label": "Low" if any_overfit else "High",
                        }
                    )

        # Sort robustness data by main score descending and take top 10
        robustness_data.sort(key=lambda x: x["main_score"], reverse=True)
        robustness_data = robustness_data[:10]

        # Render Template
        template = Template(REPORT_TEMPLATE)
        html_content = template.render(
            run=run,
            baseline_candidate=baseline_candidate,
            best_candidate=best_candidate,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            scores_json=json.dumps(scores),
            labels_json=json.dumps(labels),
            robustness_data=robustness_data,
        )

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        print(f"Report generated: {output_path}")
