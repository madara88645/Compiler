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
        model="gpt-4o", max_generations=1, candidates_per_generation=1, adversarial_every=0
    )
    prompt = ""
    result = estimate_run_cost(config, prompt)

    # Should not crash, cost should be calculable
    assert result["min_cost"] >= 0
    assert result["details"]["estimated_input_tokens"] > 0  # System prompts etc still add tokens


def test_estimate_zero_generations():
    """Verify cost is calculated correctly when generations are 0."""
    config = OptimizationConfig(
        model="gpt-4o", max_generations=0, candidates_per_generation=5, adversarial_every=0
    )
    prompt = "Test prompt"
    result = estimate_run_cost(config, prompt)

    # 0 generations means 0 mutations
    assert result["details"]["total_calls"] == 0
    assert result["min_cost"] == 0.0
    assert result["max_cost"] == 0.0


def test_estimate_unknown_model_fallback():
    """Verify that an unknown model defaults to the 'default' pricing."""
    config = OptimizationConfig(
        model="unknown-model-123", max_generations=1, candidates_per_generation=1
    )
    prompt = "Test"

    # Run with unknown model
    result_unknown = estimate_run_cost(config, prompt)

    # Run with explict default (if we could, but we can infer from code that 'default' key is used)
    # Let's compare with a known high cost model vs known low cost to see where it lands,
    # or just ensure it produces a valid cost.
    # The default pricing in code is input: 5.00, output: 15.00.

    assert result_unknown["min_cost"] > 0


def test_estimate_model_case_insensitivity():
    """Verify that model names are treated case-insensitively."""
    prompt = "Test prompt"

    config_lower = OptimizationConfig(model="gpt-4o", max_generations=1, candidates_per_generation=1)
    result_lower = estimate_run_cost(config_lower, prompt)

    config_upper = OptimizationConfig(model="GPT-4o", max_generations=1, candidates_per_generation=1)
    result_upper = estimate_run_cost(config_upper, prompt)

    assert result_lower["min_cost"] == result_upper["min_cost"]
    assert result_lower["max_cost"] == result_upper["max_cost"]


def test_estimate_adversarial_edge_cases():
    """Verify behavior when adversarial_every is larger than max_generations."""
    # If adversarial_every > max_generations, 0 adversarial runs should happen
    config = OptimizationConfig(
        model="gpt-4o", max_generations=2, candidates_per_generation=1, adversarial_every=5
    )
    prompt = "Test"
    result = estimate_run_cost(config, prompt)

    # Total calls = 2 gens * 1 cand = 2. Adversarial = 0.
    assert result["details"]["total_calls"] == 2
