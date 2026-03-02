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


def test_estimate_empty_prompt():
    """Verify behavior with an empty string prompt."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=1, candidates_per_generation=1
    )
    prompt = ""
    result = estimate_run_cost(config, prompt)

    # Should not crash, cost should be low but cover system prompts
    assert result["min_cost"] > 0
    assert result["details"]["estimated_input_tokens"] > 0


def test_estimate_zero_generations():
    """Verify behavior when max_generations is 0."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=0, candidates_per_generation=5
    )
    prompt = "Test"
    result = estimate_run_cost(config, prompt)

    assert result["details"]["total_calls"] == 0
    assert result["min_cost"] == 0.0


def test_estimate_zero_candidates():
    """Verify behavior when candidates_per_generation is 0."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=5, candidates_per_generation=0
    )
    prompt = "Test"
    result = estimate_run_cost(config, prompt)

    assert result["details"]["total_calls"] == 0
    assert result["min_cost"] == 0.0


def test_estimate_unknown_model():
    """Verify fallback to default pricing for unknown models."""
    config = OptimizationConfig(
        model="unknown-model-123", max_generations=1, candidates_per_generation=1
    )
    prompt = "Test"
    result = estimate_run_cost(config, prompt)

    # Should use default pricing (GPT-4o equivalent in code)
    assert result["min_cost"] > 0
    assert "unknown-model-123" in result["message"]


def test_estimate_adversarial_sparse():
    """Verify behavior when adversarial_every is larger than max_generations."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=2, candidates_per_generation=1, adversarial_every=5
    )
    prompt = "Test"
    result = estimate_run_cost(config, prompt)

    # 2 gens * 1 cand = 2 calls
    # adversarial_runs = 2 // 5 = 0
    assert result["details"]["total_calls"] == 2


def test_estimate_large_prompt():
    """Verify behavior with a very large prompt."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=1, candidates_per_generation=1
    )
    # 10k characters
    prompt = "a" * 10000
    result = estimate_run_cost(config, prompt)

    assert result["min_cost"] > 0
    # Basic sanity check that tokens are accounted for
    assert result["details"]["estimated_input_tokens"] > 2500  # > 10000/4
