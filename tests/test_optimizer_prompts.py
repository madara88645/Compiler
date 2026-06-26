import pytest
from app.optimizer.prompts import get_strategy_prompt, list_strategies, STRATEGY_PROMPTS


def test_list_strategies():
    strategies = list_strategies()
    # Check that it returns the expected list of unique, non-alias strategies
    expected = [
        "compressor",
        "cot",
        "persona",
        "structurer",
        "exemplar",
        "constraint",
        "simplifier",
    ]
    assert sorted(strategies) == sorted(expected)


def test_get_strategy_prompt_valid():
    # Test valid strategy prompts and aliases
    assert get_strategy_prompt("compressor") == STRATEGY_PROMPTS["compressor"]
    assert get_strategy_prompt("cot") == STRATEGY_PROMPTS["cot"]
    assert get_strategy_prompt("chain-of-thought") == STRATEGY_PROMPTS["chain_of_thought"]
    assert get_strategy_prompt("PERSONA") == STRATEGY_PROMPTS["persona"]


def test_get_strategy_prompt_invalid():
    # Test that invalid strategy names raise KeyError
    with pytest.raises(KeyError) as exc_info:
        get_strategy_prompt("nonexistent_strategy")

    assert "Unknown strategy 'nonexistent_strategy'" in str(exc_info.value)
    # Check that available strategies are listed in the error message
    assert "compressor" in str(exc_info.value)
