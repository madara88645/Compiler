from unittest.mock import patch

import pytest

from app.optimizer.costs import CostTracker, PricingModel, TokenCounter


class TestTokenCounter:
    def test_count_known_model(self):
        with patch("app.optimizer.costs.tiktoken.encoding_for_model") as mock_encoding_for_model, patch(
            "app.optimizer.costs.tiktoken.get_encoding"
        ) as mock_get_encoding:
            mock_encoding_for_model.return_value.encode.return_value = [1, 2, 3, 4]

            text = "Hello, world!"
            count = TokenCounter.count(text, "gpt-4o")

            mock_encoding_for_model.assert_called_once_with("gpt-4o")
            mock_get_encoding.assert_not_called()
            assert count == 4

    def test_count_unknown_model(self):
        text = "Hello world!"
        # For an unknown model, TokenCounter should fall back to cl100k_base encoding.
        # Mock tiktoken so we deterministically verify the fallback behavior.
        with patch("app.optimizer.costs.tiktoken.encoding_for_model") as mock_encoding_for_model, patch(
            "app.optimizer.costs.tiktoken.get_encoding"
        ) as mock_get_encoding:
            mock_encoding_for_model.side_effect = KeyError("unknown model")

            mock_encoding = mock_get_encoding.return_value
            mock_encoding.encode.return_value = [1, 2, 3]

            count = TokenCounter.count(text, "unknown-model-xyz")

            mock_encoding_for_model.assert_called_once_with("unknown-model-xyz")
            mock_get_encoding.assert_called_once_with("cl100k_base")
            mock_encoding.encode.assert_called_once_with(text)
            assert count == 3
        # For an unknown model, TokenCounter should fall back to cl100k_base encoding.
        # Mock tiktoken so we deterministically verify the fallback behavior.
        with patch("app.optimizer.costs.tiktoken.encoding_for_model") as mock_encoding_for_model, \
             patch("app.optimizer.costs.tiktoken.get_encoding") as mock_get_encoding:
            # Simulate tiktoken not knowing this model
            mock_encoding_for_model.side_effect = KeyError("unknown model")

            # Configure the fallback encoding to return a known tokenization
            mock_encoding = mock_get_encoding.return_value
            mock_encoding.encode.return_value = [1, 2, 3]

            count = TokenCounter.count(text, "unknown-model-xyz")

            # Verify that the unknown model path was taken first
            mock_encoding_for_model.assert_called_once_with("unknown-model-xyz")
            # And that we fell back to cl100k_base
            mock_get_encoding.assert_called_once_with("cl100k_base")
            mock_encoding.encode.assert_called_once_with(text)

            # The count should equal the length of the mocked token list
            assert count == 3
class TestCostTracker:
    def test_initial_state(self):
        tracker = CostTracker()
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.total_cost == 0.0
        assert tracker.estimated_cost() == 0.0

    @patch("app.optimizer.costs.PricingModel.get_rate")
    def test_add_usage(self, mock_get_rate):
        mock_get_rate.return_value = (5.0, 15.0)  # input_rate, output_rate

        tracker = CostTracker()
        tracker.add_usage(1000, 2000, "gpt-4o")

        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 2000

        # cost = (1000/1000000)*5.0 + (2000/1000000)*15.0 = 0.005 + 0.03 = 0.035
        expected_cost = 0.035
        assert abs(tracker.total_cost - expected_cost) < 1e-9
        assert abs(tracker.estimated_cost() - expected_cost) < 1e-9

    @patch("app.optimizer.costs.PricingModel.get_rate")
    def test_add_usage_multiple(self, mock_get_rate):
        # We will return the same rate for simplicity in testing the accumulation
        mock_get_rate.return_value = (5.0, 15.0)

        tracker = CostTracker()

        # Call 1
        tracker.add_usage(1000, 2000, "gpt-4o")
        # Call 2
        tracker.add_usage(500, 1000, "gpt-4o")

        assert tracker.total_input_tokens == 1500
        assert tracker.total_output_tokens == 3000

        # cost = (1500/1000000)*5.0 + (3000/1000000)*15.0 = 0.0075 + 0.045 = 0.0525
        expected_cost = 0.0525
        assert abs(tracker.total_cost - expected_cost) < 1e-9
        assert abs(tracker.estimated_cost() - expected_cost) < 1e-9

    @patch("app.optimizer.costs.PricingModel.get_rate")
    def test_add_usage_unknown_model(self, mock_get_rate):
        mock_get_rate.return_value = (0.0, 0.0)

        tracker = CostTracker()
        tracker.add_usage(1_000_000, 1_000_000, "unknown-model")

        assert tracker.total_input_tokens == 1_000_000
        assert tracker.total_output_tokens == 1_000_000
        assert tracker.estimated_cost() == 0.0


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
            sorted_keys = sorted(mock_rates_data.keys(), key=len, reverse=True)
            with patch.object(PricingModel, "_SORTED_KEYS", sorted_keys):
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
            # Ensure the cached sorted keys match the mocked rates so these tests
            # do not depend on PricingModel's cache-mismatch fallback behavior.
            with patch.object(PricingModel, "_SORTED_KEYS", list(mock_rates_data.keys())):
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
