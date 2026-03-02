import pytest
from unittest.mock import patch
from app.optimizer.costs import PricingModel, TokenCounter, CostTracker


class TestTokenCounter:
    def test_count_known_model(self):
        text = "Hello world!"
        # This will use the specific encoding for gpt-4
        count = TokenCounter.count(text, "gpt-4")
        assert count > 0  # Should be 3 tokens for 'Hello', ' world', '!' typically

    def test_count_unknown_model(self):
        text = "Hello world!"
        # This will fallback to cl100k_base encoding
        count = TokenCounter.count(text, "unknown-model-xyz")
        assert count > 0


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
    @pytest.fixture(autouse=True)
    def mock_rates(self):
        mock_rates_data = {
            "gpt-4o": {"input": 5.0, "output": 15.0},
        }
        with patch.dict(PricingModel.RATES, mock_rates_data, clear=True):
            yield

    def test_add_usage_known_model(self):
        tracker = CostTracker()
        tracker.add_usage(1_000_000, 2_000_000, "gpt-4o")

        assert tracker.total_input_tokens == 1_000_000
        assert tracker.total_output_tokens == 2_000_000

        # input: (1M / 1M) * 5.0 = 5.0
        # output: (2M / 1M) * 15.0 = 30.0
        # total: 35.0
        assert tracker.estimated_cost() == 35.0

    def test_add_usage_unknown_model(self):
        tracker = CostTracker()
        tracker.add_usage(1_000_000, 1_000_000, "unknown-model")

        assert tracker.total_input_tokens == 1_000_000
        assert tracker.total_output_tokens == 1_000_000

        # Falls back to 0.0 rate
        assert tracker.estimated_cost() == 0.0
