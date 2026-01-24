"""
Analytics extraction for optimization runs.
Prepares data for visualization libraries like Chart.js.
"""

from __future__ import annotations
from typing import Dict, Any, List
from collections import defaultdict
import statistics

from app.optimizer.models import OptimizationRun, Candidate


def extract_score_history(run: OptimizationRun) -> Dict[str, Any]:
    """
    Extracts score history per generation for Chart.js.

    Returns:
        Dict with "labels" (Gen X) and "datasets" (Max Score, Avg Score).
    """
    labels = []
    max_scores = []
    avg_scores = []

    for i, generation in enumerate(run.generations):
        labels.append(f"Gen {i}")

        scores = [c.score for c in generation if c.result]
        if scores:
            max_scores.append(max(scores))
            avg_scores.append(statistics.mean(scores))
        else:
            max_scores.append(0.0)
            avg_scores.append(0.0)

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Max Score",
                "data": max_scores,
                "borderColor": "rgb(75, 192, 192)",
                "tension": 0.1,
                "fill": False,
            },
            {
                "label": "Average Score",
                "data": avg_scores,
                "borderColor": "rgb(255, 159, 64)",
                "tension": 0.1,
                "fill": False,
            },
        ],
    }


def analyze_strategy_performance(run: OptimizationRun) -> Dict[str, Any]:
    """
    Analyzes performance by mutation strategy.

    Returns:
        Dict suitable for a Bar Chart: labels (strategies), data (avg improvement or score).
    """
    # 1. Build candidate lookup for parent retrieval
    candidate_map: Dict[str, Candidate] = {}
    for generation in run.generations:
        for cand in generation:
            candidate_map[cand.id] = cand

    # 2. Collect stats per strategy
    strategy_stats = defaultdict(list)

    for generation in run.generations:
        for cand in generation:
            if cand.mutation_type in ("initial", "baseline", "human_intervention"):
                continue

            # Calculate improvement over parent
            improvement = 0.0
            if cand.parent_id and cand.parent_id in candidate_map:
                parent = candidate_map[cand.parent_id]
                improvement = cand.score - parent.score

            # Or just use raw score? Improvement is better for strategy effectiveness.
            # But high scores matter more. Let's track both if needed, but for the chart
            # let's map "Average Score" per strategy.
            strategy_stats[cand.mutation_type].append(cand.score)

    # 3. Aggregate
    labels = []
    data = []
    counts = []

    for strategy, scores in strategy_stats.items():
        labels.append(strategy)
        data.append(statistics.mean(scores))
        counts.append(len(scores))

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Average Score by Strategy",
                "data": data,
                "backgroundColor": [
                    "rgba(255, 99, 132, 0.2)",
                    "rgba(54, 162, 235, 0.2)",
                    "rgba(255, 206, 86, 0.2)",
                    "rgba(75, 192, 192, 0.2)",
                    "rgba(153, 102, 255, 0.2)",
                ],
                "borderColor": [
                    "rgba(255, 99, 132, 1)",
                    "rgba(54, 162, 235, 1)",
                    "rgba(255, 206, 86, 1)",
                    "rgba(75, 192, 192, 1)",
                    "rgba(153, 102, 255, 1)",
                ],
                "borderWidth": 1,
            }
        ],
        "metadata": {"counts": dict(zip(labels, counts))},
    }
