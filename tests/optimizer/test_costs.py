import pytest
from unittest.mock import patch
from app.optimizer.costs import PricingModel, TokenCounter, CostTracker


class TestTokenCounter:
    def test_count_known_model(self):
        text = "Hello, world!"
        # gpt-4o should be known and use o200k_base or cl100k_base depending on tiktoken version,
        # but the test is just that it counts correctly without error.
        count = TokenCounter.count(text, "gpt-4o")
        assert count > 0

    def test_count_unknown_model_fallback(self):
        text = "Hello, world!"
        # "unknown-model" should fallback to cl100k_base
        count = TokenCounter.count(text, "unknown-model")
        assert count > 0

        # We can also compare it to an explicit cl100k_base encoding count to be sure
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        expected_count = len(encoding.encode(text))
        assert count == expected_count


class TestPricingModel:
    @pytest.fixture(autouse=True)
    def mock_rates(self):
        """
        Mock the RATES dictionary to ensure tests test the logic, not the data.
        Also explicitly set _SORTED_KEYS to match the mocked rates to test the fallback logic.
        """
        mock_rates_data = {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.6},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            "test-model": {"input": 1.0, "output": 2.0},
            "test-model-v2": {"input": 3.0, "output": 4.0},
        }

        with patch.dict(PricingModel.RATES, mock_rates_data, clear=True):
            # We clear _SORTED_KEYS to force regeneration or test the re-sort logic
            # In the implementation, if keys differ, it re-sorts.
            yield

    @pytest.mark.parametrize(
        "model, expected_input, expected_output",
        [
            # Exact matches from mocked data
            ("gpt-4o", 5.0, 15.0),
            ("gpt-4o-mini", 0.15, 0.6),
            ("test-model", 1.0, 2.0),
            ("test-model-v2", 3.0, 4.0),
            # Prefix matches
            ("gpt-4o-2024-05-13", 5.0, 15.0),
            ("gpt-3.5-turbo-0125", 0.5, 1.5),
            ("test-model-suffix", 1.0, 2.0),
            # Unknown models
            ("unknown-model", 0.0, 0.0),
            ("gpt-5", 0.0, 0.0),
            # Edge cases
            ("", 0.0, 0.0),
        ],
    )
    def test_get_rate(self, model, expected_input, expected_output):
        input_rate, output_rate = PricingModel.get_rate(model)
        assert input_rate == expected_input
        assert output_rate == expected_output

    def test_get_rate_sorting(self):
        """
        Verify that more specific prefixes are matched before shorter prefixes.
        e.g., 'gpt-4o-mini' should match 'gpt-4o-mini' entry, not 'gpt-4o'.
        """
        # "test-model-v2" starts with "test-model".
        # If sorted incorrectly (shortest first or random), "test-model" might match "test-model-v2".

        # Case 1: "gpt-4o-mini" vs "gpt-4o"
        input_rate, output_rate = PricingModel.get_rate("gpt-4o-mini")
        assert input_rate == 0.15
        assert output_rate == 0.6

        # Case 2: "test-model-v2" vs "test-model"
        input_rate, output_rate = PricingModel.get_rate("test-model-v2")
        assert input_rate == 3.0
        assert output_rate == 4.0


class TestCostTracker:
    def test_initial_state(self):
        tracker = CostTracker()
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.total_cost == 0.0
        assert tracker.estimated_cost() == 0.0

    def test_add_usage_known_model(self):
        # Note: TestPricingModel's mock_rates fixture is scoped to TestPricingModel, so it does not apply here.
        # PricingModel.RATES has "gpt-4o-mini": {"input": 0.15, "output": 0.6}

        tracker = CostTracker()
        tracker.add_usage(input_tokens=1_000_000, output_tokens=500_000, model="gpt-4o-mini")

        # 1M input tokens at $0.15/1M = $0.15
        # 500k output tokens at $0.6/1M = $0.30
        # Total cost = $0.45
        assert tracker.total_input_tokens == 1_000_000
        assert tracker.total_output_tokens == 500_000
        assert pytest.approx(tracker.total_cost) == 0.45
        assert pytest.approx(tracker.estimated_cost()) == 0.45

        # Add more usage
        tracker.add_usage(input_tokens=500_000, output_tokens=250_000, model="gpt-4o-mini")

        # Additional: 500k input = $0.075, 250k output = $0.15. Total added: $0.225
        # New total cost: $0.675
        assert tracker.total_input_tokens == 1_500_000
        assert tracker.total_output_tokens == 750_000
        assert pytest.approx(tracker.total_cost) == 0.675
        assert pytest.approx(tracker.estimated_cost()) == 0.675

    def test_add_usage_unknown_model_fallback(self):
        # Do not mock PricingModel.get_rate, so we test the actual fallback logic returning (0.0, 0.0)
        tracker = CostTracker()
        tracker.add_usage(
            input_tokens=1_000_000, output_tokens=1_000_000, model="unknown-model-fallback"
        )

        assert tracker.total_input_tokens == 1_000_000
        assert tracker.total_output_tokens == 1_000_000
        assert tracker.total_cost == 0.0
        assert tracker.estimated_cost() == 0.0

    def test_pricing_model_get_rate_unknown_explicit(self):
        # Explicit test for PricingModel.get_rate fallback
        input_rate, output_rate = PricingModel.get_rate("totally-unknown-model")
        assert input_rate == 0.0
        assert output_rate == 0.0
