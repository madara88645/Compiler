import sys
import os

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.optimizer.models import OptimizationConfig
from app.optimizer.mutator import MutatorAgent
from app.llm.providers import MockProvider


def verify_strategies():
    print("Verifying Mutator Strategies Wiring...")

    config = OptimizationConfig()
    provider = MockProvider(None)

    # agent = MutatorAgent(config, provider) # No strategies attr anymore

    from app.optimizer.strategies import STRATEGY_REGISTRY

    strategies = list(STRATEGY_REGISTRY.keys())
    print(f"Loaded {len(strategies)} strategies in registry:")

    expected_types = ["refinement", "compressor", "chain_of_thought", "persona"]

    for s in strategies:
        print(f" - {s}")

    # Validation
    missing = [t for t in expected_types if t not in strategies]

    if missing:
        print(f"FAILED: Missing strategies: {missing}")
        sys.exit(1)

    print("SUCCESS: All expected strategies are wired up!")


if __name__ == "__main__":
    verify_strategies()
