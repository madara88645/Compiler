import pytest
from app.optimizer.costs import TokenCounter, PricingModel, CostTracker

# --- TokenCounter Tests ---

def test_token_counter_count_known_model():
    text = "Hello, world!"
    # Verify it returns a valid count for a known model
    count = TokenCounter.count(text, "gpt-4o")
    assert isinstance(count, int)
    assert count > 0

def test_token_counter_count_unknown_model():
    text = "Hello, world!"
    # This should trigger the KeyError and fallback to cl100k_base
    count = TokenCounter.count(text, "fake-model-123")
    assert isinstance(count, int)
    assert count > 0

# --- PricingModel Tests ---

def test_pricing_model_get_rate_known_models():
    # gpt-4o
    input_rate, output_rate = PricingModel.get_rate("gpt-4o")
    assert input_rate == 5.0
    assert output_rate == 15.0

    # gpt-4o substring match check (e.g. gpt-4o-2024...)
    # The code uses startswith.
    input_rate, output_rate = PricingModel.get_rate("gpt-4o-custom")
    assert input_rate == 5.0
    assert output_rate == 15.0

    # gpt-4o-mini
    input_rate, output_rate = PricingModel.get_rate("gpt-4o-mini")
    assert input_rate == 0.15
    assert output_rate == 0.6

    # gpt-3.5-turbo
    input_rate, output_rate = PricingModel.get_rate("gpt-3.5-turbo")
    assert input_rate == 0.5
    assert output_rate == 1.5

def test_pricing_model_get_rate_unknown_model():
    input_rate, output_rate = PricingModel.get_rate("unknown-model")
    assert input_rate == 0.0
    assert output_rate == 0.0

# --- CostTracker Tests ---

def test_cost_tracker_initialization():
    tracker = CostTracker()
    assert tracker.total_input_tokens == 0
    assert tracker.total_output_tokens == 0
    assert tracker.total_cost == 0.0
    assert tracker.estimated_cost() == 0.0

def test_cost_tracker_add_usage():
    tracker = CostTracker()

    # 1 million tokens for easy math
    # gpt-4o: input 5.0, output 15.0
    # Input: 1M -> $5.0
    # Output: 1M -> $15.0
    tracker.add_usage(1_000_000, 1_000_000, "gpt-4o")

    assert tracker.total_input_tokens == 1_000_000
    assert tracker.total_output_tokens == 1_000_000
    assert tracker.estimated_cost() == pytest.approx(20.0)

    # Add more usage
    # gpt-3.5-turbo: input 0.5, output 1.5
    tracker.add_usage(1_000_000, 1_000_000, "gpt-3.5-turbo")

    assert tracker.total_input_tokens == 2_000_000
    assert tracker.total_output_tokens == 2_000_000
    # Previous 20.0 + (0.5 + 1.5) = 22.0
    assert tracker.estimated_cost() == pytest.approx(22.0)

def test_cost_tracker_unknown_model_usage():
    tracker = CostTracker()
    tracker.add_usage(100, 100, "unknown")
    assert tracker.total_input_tokens == 100
    assert tracker.total_output_tokens == 100
    assert tracker.estimated_cost() == 0.0
