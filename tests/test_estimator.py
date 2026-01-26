"""Tests for Cost Estimator."""

from app.optimizer.estimator import estimate_run_cost
from app.optimizer.models import OptimizationConfig


def test_estimate_run_cost_basic():
    """Verify basic cost estimation structure and output."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=3, candidates_per_generation=3, adversarial_every=0
    )
    prompt = "Simple prompt"

    result = estimate_run_cost(config, prompt)

    assert "min_cost" in result
    assert "max_cost" in result
    assert "message" in result
    assert result["min_cost"] > 0
    assert result["max_cost"] > result["min_cost"]

    # 3 gens * 3 cands = 9 calls + 0 adversarial = 9 calls.
    # Cost should be small but non-zero.
    print(f"\nEstimated: {result['message']}")


def test_estimate_run_cost_adversarial():
    """Verify adversarial cost inclusion."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=4, candidates_per_generation=2, adversarial_every=2
    )
    # Gens: 1, 2, 3, 4.
    # Adversarial at 2, 4 = 2 runs.
    # Total mutations = 4 * 2 = 8.
    # Total calls = 8 + 2 = 10.

    prompt = "Simple prompt"
    result = estimate_run_cost(config, prompt)

    assert result["details"]["total_calls"] == 10
