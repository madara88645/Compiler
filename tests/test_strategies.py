import json
import unittest
from unittest.mock import MagicMock
from app.optimizer.models import OptimizationConfig, Candidate
from app.optimizer.mutator import MutatorAgent
from app.optimizer.strategies import CompressorStrategy, CoTStrategy, PersonaStrategy


class TestSmartStrategies(unittest.TestCase):
    def setUp(self):
        self.config = OptimizationConfig(available_strategies=["compressor", "chain_of_thought"])
        self.mock_provider = MagicMock()
        self.mutator = MutatorAgent(self.config, provider=self.mock_provider)
        self.parent = Candidate(generation=0, prompt_text="Do X.", mutation_type="base")

    def test_compressor_strategy(self):
        # Mock LLM response
        self.mock_provider.generate.return_value.content = json.dumps(
            {"type": "compressed", "prompt": "Do X quickly."}
        )

        strategy = CompressorStrategy()
        result = strategy.mutate(self.parent, self.mock_provider)
        self.assertEqual(result, "Do X quickly.")

    def test_cot_strategy_fallback(self):
        # Test without provider (deterministic fallback)
        strategy = CoTStrategy()
        result = strategy.mutate(self.parent, None)
        self.assertIn("Let's think step by step", result)

    def test_mutator_integration(self):
        # Mock LLM to return valid JSON for calls
        self.mock_provider.generate.return_value.content = json.dumps({"prompt": "Mutated"})

        # Should generate candidates using the configured strategies
        candidates = self.mutator.generate_variations(self.parent, [])

        # Expect 3 candidates by default config
        self.assertEqual(len(candidates), 3)

        # Check output types (round robin of compressor, cot)
        types = [c.mutation_type for c in candidates]
        self.assertIn("compressor", types)
        self.assertIn("chain_of_thought", types)
