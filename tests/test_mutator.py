"""Tests for MutatorAgent and Mutation Strategies."""

import pytest
from unittest.mock import MagicMock
from app.optimizer.mutator import MutatorAgent
from app.optimizer.models import OptimizationConfig, Candidate
from app.optimizer.strategies import (
    CompressorStrategy,
    CoTStrategy,
    PersonaStrategy,
    get_strategy,
    STRATEGY_REGISTRY,
)
from app.llm.base import LLMProvider, LLMResponse, ProviderConfig


@pytest.fixture
def config():
    return OptimizationConfig()


@pytest.fixture
def parent():
    return Candidate(generation=0, prompt_text="Base prompt text", mutation_type="initial")


class TestStrategies:
    """Test individual strategy classes."""

    def test_compressor_strategy_mock(self, parent):
        """Verify CompressorStrategy works without LLM."""
        strategy = CompressorStrategy()
        result = strategy.mutate(parent, provider=None)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_cot_strategy_mock(self, parent):
        """Verify CoTStrategy injects chain-of-thought."""
        strategy = CoTStrategy()
        result = strategy.mutate(parent, provider=None)

        assert "step by step" in result.lower()
        assert parent.prompt_text in result

    def test_persona_strategy_mock(self, parent):
        """Verify PersonaStrategy adds persona prefix."""
        strategy = PersonaStrategy()
        result = strategy.mutate(parent, provider=None)

        assert "expert" in result.lower() or "you are" in result.lower()

    def test_get_strategy_valid(self):
        """Test get_strategy returns correct instances."""
        assert isinstance(get_strategy("compressor"), CompressorStrategy)
        assert isinstance(get_strategy("chain_of_thought"), CoTStrategy)
        assert isinstance(get_strategy("persona"), PersonaStrategy)

    def test_get_strategy_invalid(self):
        """Test get_strategy raises for unknown."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("nonexistent")


class TestMutatorAgent:
    """Test MutatorAgent with strategies."""

    def test_mutator_uses_configured_strategies(self, config, parent):
        """Verify MutatorAgent uses strategies from config."""
        config.available_strategies = ["compressor", "persona"]
        config.candidates_per_generation = 2
        agent = MutatorAgent(config)

        results = agent.generate_variations(parent, failures=[])

        assert len(results) == 2
        types = [c.mutation_type for c in results]
        assert "compressor" in types
        assert "persona" in types

    def test_mutator_round_robin(self, config, parent):
        """Verify round-robin strategy selection."""
        config.available_strategies = ["compressor", "chain_of_thought", "persona"]
        config.candidates_per_generation = 3
        agent = MutatorAgent(config)

        results = agent.generate_variations(parent, failures=[])
        types = [c.mutation_type for c in results]

        # All three strategies should be used
        assert "compressor" in types
        assert "chain_of_thought" in types
        assert "persona" in types

    def test_mutator_fallback_on_error(self, config, parent):
        """Verify fallback when all strategies fail."""
        config.available_strategies = ["nonexistent"]
        config.candidates_per_generation = 1
        agent = MutatorAgent(config)

        results = agent.generate_variations(parent, failures=[])

        # Should get fallback candidate
        assert len(results) == 1
        assert results[0].mutation_type == "fallback"
